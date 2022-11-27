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
    offset = 0
    index = 0

    # 0. get doc_count via https://replicate.npmjs.com/
    r = requests.get("https://replicate.npmjs.com/")
    # total_packages = r.json().get("doc_count")
    total_packages = r.json().get("doc_count")

    with open(f'data.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["index", "id", "name", "description", "npm_readme", "gh_readme", "author", "final_score", "quality",
                            "popularity", "maintenance", "search_score", "stargazers_count", "watchers_count", "forks_count"])

    for _ in range(math.ceil(total_packages / PACKAGES_PER_PAGE)):
        # 1. crawl 10 packages by https://replicate.npmjs.com/_all_docs?limit=10
        r = requests.get(
            f"https://replicate.npmjs.com/_all_docs?limit={PACKAGES_PER_PAGE}&skip={offset}")        
        offset += PACKAGES_PER_PAGE
        ids = list(map(lambda package: package.get("id"), r.json().get("rows")))

        # 2. for each package take the id or key and then call the following link: https://registry.npmjs.org/{key}
        for id in ids:
            row = []
            r = requests.get(f"https://registry.npmjs.org/{id}")

            #   2.a Save id, name, description, latest dist-tags readme and github homepage readme
            package = r.json()
            name = package.get("name")
            latest = package.get("dist-tags").get("latest")
            description = package.get("versions").get(
                latest).get("description")
            npm_readme = package.get("readme")
            gh_readme_url = package.get("homepage")
            author = package.get("author", {"name": ""}).get("name")

            if npm_readme == "ERROR: No README data found!":
                npm_readme = ""

            # 3. for each package take the id or key and then call the following link: https://registry.npmjs.org/-/v1/search?text={key}
            r = requests.get(
                f"https://registry.npmjs.org/-/v1/search?text={re.sub('[^A-Za-z0-9]+', '', id)}")
            objects = r.json().get("objects")
            scores = [0] * 5
            for obj in objects:
                #   3.a If package is the same name => save keywords
                #   3.a final score, quality, popularity, maintenance, searchScore
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

                r = requests.get(url, headers=headers)
                if r.status_code == 200:
                    download_url = r.json().get("download_url")
                    r = requests.get(download_url)
                    gh_readme = r.text
                else:
                    gh_readme = ""

                # 5 Use the homepage url to call to https://api.github.com/repos/<user>/<repo_name> to get stargazers_count, forks, watchers
                r = requests.get(url[:-19], headers=headers)
                if r.status_code == 200:
                    obj = r.json()
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
            with open(f'data.csv', 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(row)

        print("Sleep")
        time.sleep(2)
