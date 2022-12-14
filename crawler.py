import json
import time
import requests
import re
import math
import csv
import socket
import requests.packages.urllib3.util.connection as urllib3_cn
from dotenv import dotenv_values

config = dotenv_values(".env")
GH_ACCESS_TOKEN = config.get("GH_ACCESS_TOKEN")


def allowed_gai_family():
    family = socket.AF_INET    # force IPv4
    return family


urllib3_cn.allowed_gai_family = allowed_gai_family


PACKAGES_PER_PAGE = 100


def run():
    print("Start running")
    with open(f'data.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["index", "id", "name", "description", "npm_readme", "gh_readme", "author", "final_score", "quality",
                         "popularity", "maintenance", "search_score", "stargazers_count", "watchers_count", "forks_count"])

    print(">>>> 1. request to https://replicate.npmjs.com/_all_docs")
    # 1. crawl all packages by https://replicate.npmjs.com/_all_docs stream = True
    all_docs_request = requests.get(
        f"https://replicate.npmjs.com/_all_docs", stream=True)
    all_docs_request.raw.chunked = True
    all_docs_request.encoding = 'utf-8'

    is_first_line = True
    index = 0

    print(">>>> Request streaming")
    for line in all_docs_request.iter_lines():
        print(f">>>> Line: {index + 1}")
        if is_first_line or not line:
            is_first_line = False
            continue

        decoded_line = line.decode('utf-8')[:-1]
        package_metadata_dict = json.loads(decoded_line)
        id = package_metadata_dict.get('id')
        # 2. for each package take the id or key and then call the following link: https://registry.npmjs.org/{key}
        row = []

        print(">>>> Package detail request")
        package_request = requests.get(f"https://registry.npmjs.org/{id}")
        package_request.raw.chunked = True
        package_request.encoding = 'utf-8'

        #   2.a Save id, name, description, latest dist-tags readme and github homepage readme
        package_dict = package_request.json()
        name = package_dict.get("name")
        latest = package_dict.get("dist-tags").get("latest")
        description = package_dict.get("versions").get(
            latest).get("description")
        npm_readme = package_dict.get("readme")
        gh_readme_url = package_dict.get("homepage")
        author = package_dict.get("author", {"name": ""}).get("name")

        if npm_readme == "ERROR: No README data found!":
            npm_readme = ""

        # 3. for each package take the id or key and then call the following link: https://registry.npmjs.org/-/v1/search?text={key}
        print(">>>> Search request")
        search_request = requests.get(
            f"https://registry.npmjs.org/-/v1/search?text={re.sub('[^A-Za-z0-9]+', '', id)}")
        search_request.raw.chunked = True
        search_request.encoding = 'utf-8'

        objects = search_request.json().get("objects")
        scores = [0] * 5
        for obj in objects:
            #   3.a If package is the same name => save keywords
            #   3.b final score, quality, popularity, maintenance, searchScore
            package = obj.get("package")
            score = obj.get("score")
            final_score = score.get("final")
            detail_score = score.get("detail")
            quality = detail_score.get("quality")
            popularity = detail_score.get("popularity")
            maintenance = detail_score.get("maintenance")
            search_score = obj.get("searchScore")

            if package.get("name") == name:
                scores = [final_score, quality,
                          popularity, maintenance, search_score]
                break

        # 4 Use the homepage url to call to https://api.github.com/repos/<user>/<repo_name>/contents/README.md and call to download_url to download the file
        if gh_readme_url is not None:
            hash_index = gh_readme_url.find("#")
            if hash_index == -1:
                url = f"https://api.github.com/repos/{gh_readme_url[19:]}/contents/README.md"
            else:
                url = f"https://api.github.com/repos/{gh_readme_url[19:hash_index]}/contents/README.md"
            headers = {"Authorization": f"Bearer {GH_ACCESS_TOKEN}"}

            print(">>>> readme request")
            readme_request = requests.get(url, headers=headers)
            readme_request.raw.chunked = True
            readme_request.encoding = 'utf-8'

            if readme_request.status_code == 200:
                download_url = readme_request.json().get("download_url")
                readme_request = requests.get(download_url)
                readme_request.raw.chunked = True
                readme_request.encoding = 'utf-8'

                gh_readme = readme_request.text
            else:
                gh_readme = ""

            # 5 Use the homepage url to call to https://api.github.com/repos/<user>/<repo_name> to get stargazers_count, forks, watchers
            print(">>>> Stats request")
            stats_request = requests.get(url[:-19], headers=headers)
            stats_request.raw.chunked = True
            stats_request.encoding = 'utf-8'

            if stats_request.status_code == 200:
                obj = stats_request.json()
                stargazers_count = obj.get("stargazers_count")
                watchers_count = obj.get("watchers_count")
                forks_count = obj.get("forks_count")
            else:
                stargazers_count = 0
                watchers_count = 0
                forks_count = 0
        else:
            gh_readme = ""
            stargazers_count = 0
            watchers_count = 0
            forks_count = 0

        index += 1
        row += [index, id, name, description, npm_readme, gh_readme, author] + \
            scores + [stargazers_count, watchers_count, forks_count]
        print(f"Done fetching data: \n{row}")
        with open(f'data.csv', 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(row)
        print("===================================================================")

    print("End running")
