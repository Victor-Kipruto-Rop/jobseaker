from urllib.request import urlopen
import json

def main():
    for url in ("http://127.0.0.1:8000/health", "http://127.0.0.1:8000/health/ready"):
        with urlopen(url, timeout=5) as response:
            print(url, response.status, json.loads(response.read()))

if __name__ == "__main__":
    main()
