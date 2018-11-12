from datetime import datetime
from dateutil.relativedelta import relativedelta
from sys import stderr
from urllib.parse import urlparse
import os, tempfile
import json
import requests
import yaml


# Read the YAML config file and return a hash.
def read_config(config_file):
    with open(config_file, 'r') as y:
        config = yaml.load(y)

        return config

# Sanity check the config. Set sane defaults where possible; bail if not.
def sanity_check(config):

    # No sane defaults; bail!
    if not 'github_token' in config:
        stderr.write('Need to specify "github_token" in config.\n')
        exit(1)

    # Defaults…
    if not 'temp_dir' in config:
        config['temp_dir'] = tempfile.mkdtemp()

    if not 'libraries_src' in config:
        config['libraries_src'] = 'https://raw.githubusercontent.com/DataDog/documentation/master/data/libraries.yaml'

    if not 'output_dir' in config:
        config['output_dir'] = './output'

    return config

# Download a non-binary file from an HTTP target.
def text_downloader(url, target):
    print('Attempting to download ' + url)
    with open(target, 'wb') as f:
        r = requests.get(url, stream=True)

        if not r.ok:
            stderr.write('Could not download ' + url)
            f.close()
            os.remove(target)
            exit(1)

        for block in r.iter_content(chunk_size=128):
            if not block:
                break

            f.write(block)

    print('Downloaded ' + target)

# Process the libraries.yaml and load into a handy dict.
def process_libraries(src):
    # First read in the entire YAML
    with open(src, 'r') as stream:
        try:
            y = yaml.load(stream)
        except yaml.YAMLError as e:
            stderr.write(e)
            exit(1)

    return y

# Extract a list of URLs to check. n.b. This reads the table; the list of stuff
# under "Community Integrations" is plain markdown in a different file…
def extract_urls(y):
    urls = {}
    for top in y:
        for language in y[top]:
            for obj in language:
                for lib in language[obj]:
                    o = urlparse(lib['link'])
                    if not o.netloc in urls:
                        urls[o.netloc] = []

                    urls[o.netloc].append(lib['link'])

    return urls

# Construct GitHub API requests from the URL list, then query for Very Useful
# Information.
def hello_github(urls, token):

    projects = []

    for project_url in urls:
        extract = project_url.split('/')
        repos_api_url = 'https://api.github.com/repos/' + extract[3] + '/' + extract[4]
        obj = {
            'project_url': project_url,
            'repos_api_url': repos_api_url,
            '_name': extract[4]
            }
        projects.append(obj)

    # Stuff for the request
    p = {'access_token': token}
    h = {'Accept': 'application/vnd.github.v3+json'}

    for project in projects:
        print('Processing: ' + project['project_url'])

        # List the top contributors.
        # https://developer.github.com/v3/repos/#list-contributors
        r = requests.get(project['repos_api_url'].strip() + '/contributors', params=p, headers=h)
        body = json.loads(r.text)

        # Note the top contributors for the project.
        project['contributors'] = {}

        for contributor in body:
            project['contributors'][contributor['login']] = contributor['contributions']

        # Yoink the previous three months of commits.
        three_months_ago = datetime.now() - relativedelta(months=3)
        stamp = three_months_ago.replace(microsecond=0).isoformat() + 'Z'

        r = requests.get(project['repos_api_url'].strip() + '/commits?since=' + stamp, params=p, headers=h)
        body = json.loads(r.text)

        project['top_recents'] = {}

        for commit in body:
            try:
                if not commit['author']['login'] in project['top_recents']:
                    project['top_recents'][commit['author']['login']] = 1
                else:
                    project['top_recents'][commit['author']['login']] += 1
            # Dunno why but sometimes a "not found" SHA is returned - ignore it!
            except TypeError:
                pass

        # The API URL isn't useful anymore.
        del project['repos_api_url']

    return projects



# Ok do something useful.

# Slurp the config.
config = read_config('config.yaml')

# Sanity check the config.
config = sanity_check(config)

# Download the libraries source.
text_downloader(config['libraries_src'], config['temp_dir'] + '/libraries.yaml')

# Extract the full list of URLs from the libraries source.
list_urls = extract_urls(process_libraries(config['temp_dir'] + '/libraries.yaml'))

# Query the GitHub URLs and extract useful information.
# n.b. We're not interested in the DataDog repos…
github_urls = []

for url in list_urls['github.com']:
    if not 'github.com/DataDog' in url:
        github_urls.append(url)

github_info = hello_github(github_urls, config['github_token'])

# Write out the GitHub results.
with open(config['output_dir'] + '/github_results.yaml', 'w') as f:
    yaml.dump(github_info, f)

# And scene!
exit(0)
