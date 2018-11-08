from sys import stderr, stdout
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

    return config

# Download a non-binary file from an HTTP target.
def text_downloader(url, target):
    stdout.write('Attempting to download ' + url + '\n')
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

    stdout.write('Downloaded ' + target + '\n')

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
    # Then extract the URLs.
    urls = []
    for top in y:
        for language in y[top]:
            for obj in language:
                for lib in language[obj]:
                    # GitHub is the most popular; ignore the rest for now. :P
                    # Also, only non-Datadog repos are interesting…
                    if 'github' in lib['link']:
                        split = lib['link'].split('/')
                        if 'DataDog' not in split[3]:
                            urls.append(lib['link'])

    return urls

# Construct GitHub API requests from the URL list, then query for Very Useful
# Information.
def hello_github(urls, token):

    githubs = []

    for project_url in urls:
        extract = project_url.split('/')
        repos_api_url = 'https://api.github.com/repos/' + extract[3] + '/' + extract[4]
        obj = {'project_url': project_url, 'repos_api_url': repos_api_url }
        githubs.append(obj)

    # Stuff for the request
    p = {'access_token': token}
    h = {'Accept': 'application/vnd.github.v3+json'}

    for target in githubs:
        #r.requests.get(target['repos_api_url'].strip() + '/commits/master', params=p, headers=h)
        print(target['repos_api_url'].strip() + '/commits/master?access_token=' + token)
        #r.requests.get(target['repos_api_url'].strip() + '/contributors', params=p, headers=h)
        print(target['repos_api_url'].strip() + '/contributors?access_token=' + token)

    #return json



# Ok do something useful.

# Slurp the config.
config = read_config('config.yaml')

# Sanity check the config.
config = sanity_check(config)

# Download the libraries source.
text_downloader(config['libraries_src'], config['temp_dir'] + '/libraries.yaml')

# Extract the full list of URLs from the libraries source.
base_urls = extract_urls(process_libraries(config['temp_dir'] + '/libraries.yaml'))

# Query the urls and extract useful information!
useful_info = hello_github(base_urls, config['github_token'])
