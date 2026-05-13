#!/usr/bin/env python3
"""
Web Enumeration Tool - Endpoint & Parameter Discovery
Features:
- Endpoint enumeration: crawling, Wayback Machine, common files
- Hybrid parameter discovery: heuristic (high probability) + logarithmic batch search (low probability)
- Configurable speed/accuracy/noise profiles
- Adaptive learning of parameters across endpoints
"""

import requests
import time
import re
import json
import argparse
import sys
from urllib.parse import urljoin, urlparse, parse_qs
from collections import defaultdict
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

# ------------------------------------------------------------
#  Utility functions
# ------------------------------------------------------------
def normalize_url(url, base):
    """Convert relative URL to absolute and remove fragments."""
    absolute = urljoin(base, url)
    parsed = urlparse(absolute)
    # Remove fragment and keep only path+query
    normalized = parsed._replace(fragment="").geturl()
    return normalized

def is_same_domain(url, base_domain):
    """Check if URL belongs to the same domain."""
    return urlparse(url).netloc == base_domain

def get_baseline_response(url, session, method='GET', data=None, params=None):
    """Fetch a page without additional parameters to use as baseline."""
    try:
        if method.upper() == 'GET':
            resp = session.get(url, params=params, timeout=10)
        else:
            resp = session.post(url, data=data, timeout=10)
        return resp
    except:
        return None

def response_differs(resp1, resp2, threshold=0.05):
    """Determine if two responses differ significantly (status, length, content)."""
    if resp1 is None or resp2 is None:
        return True
    if resp1.status_code != resp2.status_code:
        return True
    # Compare content length with relative threshold
    len1, len2 = len(resp1.text), len(resp2.text)
    if len1 == len2:
        return False
    diff = abs(len1 - len2) / max(len1, len2)
    return diff > threshold

# ------------------------------------------------------------
#  Endpoint Enumerator
# ------------------------------------------------------------
class EndpointEnumerator:
    def __init__(self, base_url, session, depth=2, user_agent="Mozilla/5.0"):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.session = session
        self.depth = depth
        self.visited = set()
        self.endpoints = set()
        self.user_agent = user_agent

    def crawl(self):
        """BFS crawl to find endpoints (paths)."""
        queue = [(self.base_url, 0)]
        while queue:
            url, depth = queue.pop(0)
            if url in self.visited or depth > self.depth:
                continue
            self.visited.add(url)
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    # Add this path as endpoint
                    path = urlparse(url).path
                    if path:
                        self.endpoints.add(path)
                    # Extract links
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        absolute = normalize_url(href, url)
                        if is_same_domain(absolute, self.domain) and absolute not in self.visited:
                            queue.append((absolute, depth+1))
                time.sleep(0.5)  # politeness
            except:
                continue

    def wayback_urls(self):
        """Fetch historical URLs from Wayback Machine."""
        wayback_api = f"https://web.archive.org/cdx/search/cdx?url={self.domain}/*&output=json&collapse=urlkey"
        try:
            resp = self.session.get(wayback_api, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                # First row is header
                for row in data[1:]:
                    url = row[2]  # original URL
                    path = urlparse(url).path
                    if path and path not in self.endpoints:
                        self.endpoints.add(path)
        except:
            pass

    def common_files(self):
        """Check for common files that may reveal endpoints."""
        common = ['robots.txt', 'sitemap.xml', '.git/HEAD', '.env', 'backup.zip', 'swagger.json']
        for file in common:
            url = f"{self.base_url}/{file}"
            try:
                resp = self.session.get(url, timeout=5)
                if resp.status_code == 200:
                    self.endpoints.add(f"/{file}")
                    # Parse sitemap/robots for more links
                    if file == 'robots.txt':
                        lines = resp.text.splitlines()
                        for line in lines:
                            if line.lower().startswith('disallow:'):
                                path = line.split(':',1)[1].strip()
                                if path:
                                    self.endpoints.add(path)
                    elif file == 'sitemap.xml':
                        soup = BeautifulSoup(resp.text, 'xml')
                        for loc in soup.find_all('loc'):
                            loc_url = loc.text
                            path = urlparse(loc_url).path
                            if path:
                                self.endpoints.add(path)
            except:
                continue

    def run(self):
        """Run all endpoint enumeration strategies."""
        print("[*] Starting web crawler...")
        self.crawl()
        print(f"[+] Crawling found {len(self.endpoints)} endpoints")
        print("[*] Checking Wayback Machine...")
        self.wayback_urls()
        print(f"[+] Wayback added {len(self.endpoints)} endpoints")
        print("[*] Checking common files...")
        self.common_files()
        print(f"[+] Total endpoints discovered: {len(self.endpoints)}")

# ------------------------------------------------------------
#  Parameter Discovery – Hybrid Search
# ------------------------------------------------------------
class ParameterDiscoverer:
    def __init__(self, session, base_url, method='GET', speed='medium', accuracy='medium', noise='low'):
        self.session = session
        self.base_url = base_url
        self.method = method.upper()
        self.speed = speed
        self.accuracy = accuracy
        self.noise = noise

        # Configure parameters based on speed/accuracy
        if speed == 'fast':
            self.delay = 0.1
            self.batch_size_initial = 50
            self.batch_threshold = 10
        elif speed == 'medium':
            self.delay = 0.5
            self.batch_size_initial = 20
            self.batch_threshold = 5
        else:  # slow
            self.delay = 1.0
            self.batch_size_initial = 10
            self.batch_threshold = 3

        if accuracy == 'low':
            self.diff_threshold = 0.15
        elif accuracy == 'medium':
            self.diff_threshold = 0.08
        else:
            self.diff_threshold = 0.03

        if noise == 'low':
            self.user_agents = [self.session.headers.get('User-Agent', 'Mozilla/5.0')]
        else:
            self.user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Mozilla/5.0 (X11; Linux x86_64)'
            ]

        # Probability lists (high = common parameters)
        self.high_prob = [
            'id', 'page', 'sort', 'order', 'q', 'search', 'query', 'filter', 'limit', 'offset',
            'name', 'type', 'category', 'user', 'token', 'key', 'lang', 'format', 'callback', 'action'
        ]
        self.low_prob = []  # will be loaded from wordlist
        self.discovered = set()

    def _random_ua(self):
        if self.noise == 'low':
            self.diff_threshold = 0.15
        elif accuracy == 'medium':
            self.diff_threshold = 0.08
        else:
            self.diff_threshold = 0.03

        if noise == 'low':
            self.user_agents = [self.session.headers.get('User-Agent', 'Mozilla/5.0')]
        else:
            self.user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Mozilla/5.0 (X11; Linux x86_64)'
            ]

        # Probability lists (high = common parameters)
        self.high_prob = [
            'id', 'page', 'sort', 'order', 'q', 'search', 'query', 'filter', 'limit', 'offset',
            'name', 'type', 'category', 'user', 'token', 'key', 'lang', 'format', 'callback', 'action'
        ]
        self.low_prob = []  # will be loaded from wordlist
        self.discovered = set()

    def _random_ua(self):
        if self.noise == 'low':
            return self.user_agents[0]
        return random.choice(self.user_agents)

    def _send_request(self, url, params=None, data=None):
        """Send request with optional parameters and return response."""
        headers = {'User-Agent': self._random_ua()}
        try:
            if self.method == 'GET':
                resp = self.session.get(url, params=params, headers=headers, timeout=10)
            else:
                resp = self.session.post(url, data=data, headers=headers, timeout=10)
            time.sleep(self.delay)
            return resp
        except:
            return None

    def get_baseline(self):
        """Get baseline response (without any extra parameters)."""
        return self._send_request(self.base_url)

    def test_parameters_heuristic(self, param_list, baseline):
        """Test each parameter individually (or in small groups) using heuristic."""
        found = []
        # For speed, we can test in batches if batch_size > 1, but heuristic implies individual
        for param in param_list:
            params = {param: 'test_value'}
            resp = self._send_request(self.base_url, params=params)
            if resp and response_differs(baseline, resp, self.diff_threshold):
                found.append(param)
        return found

    def batch_test(self, param_batch, baseline):
        """Test a batch of parameters together. Returns True if response differs."""
        params = {p: 'test' for p in param_batch}
        resp = self._send_request(self.base_url, params=params)
        return response_differs(baseline, resp, self.diff_threshold)

    def logarithmic_search(self, param_list, baseline):
        """
        Recursive batch testing to find which parameters in the list are accepted.
        Returns list of discovered parameters.
        """
        if not param_list:
            return []
        if len(param_list) == 1:
            # Test individually
            params = {param_list[0]: 'test'}
            resp = self._send_request(self.base_url, params=params)
            if resp and response_differs(baseline, resp, self.diff_threshold):
                return param_list
            return []

        # Split into two halves
        mid = len(param_list) // 2
        left = param_list[:mid]
        right = param_list[mid:]

        discovered = []
        # Test left half
        if self.batch_test(left, baseline):
            discovered.extend(self.logarithmic_search(left, baseline))
        # Test right half
        if self.batch_test(right, baseline):
            discovered.extend(self.logarithmic_search(right, baseline))
        return discovered

    def discover_parameters(self, endpoints, wordlist_file=None):
        """
        Main parameter discovery routine.
        Optionally update probability lists based on endpoints.
        """
        # Load low probability wordlist if provided
        if wordlist_file:
            try:
                with open(wordlist_file, 'r') as f:
                    self.low_prob = [line.strip() for line in f if line.strip()]
            except:
                print(f"Warning: Could not read {wordlist_file}, using built-in small list")
                self.low_prob = ['p', 'value', 'data', 'json', 'callback', 'field', 'orderby']
        else:
            self.low_prob = ['p', 'value', 'data', 'json', 'callback', 'field', 'orderby']

        all_params = set()
        for endpoint in endpoints:
            url = urljoin(self.base_url, endpoint)
            print(f"[*] Testing endpoint: {url}")
            baseline = self.get_baseline()
            if baseline is None:
                continue

            # Step 1: Heuristic search on high probability list
            print(f"    Heuristic search on {len(self.high_prob)} high-probability parameters...")
            high_found = self.test_parameters_heuristic(self.high_prob, baseline)
            all_params.update(high_found)
            print(f"    Found: {high_found}")

            # Step 2: Logarithmic search on low probability list
            # Divide low_prob into batches
            low_copy = self.low_prob.copy()
            discovered_low = []
            # Process in chunks to avoid too many recursive calls
            while low_copy:
                batch = low_copy[:self.batch_size_initial]
                low_copy = low_copy[self.batch_size_initial:]
                # Test batch
                if self.batch_test(batch, baseline):
                    # Recursively find which parameters in this batch are valid
                    found_in_batch = self.logarithmic_search(batch, baseline)
                    discovered_low.extend(found_in_batch)
                    # If batch is small, move to high probability for future endpoints
                    if len(batch) <= self.batch_threshold:
                        self.high_prob.extend(found_in_batch)
                        self.high_prob = list(set(self.high_prob))  # deduplicate
            all_params.update(discovered_low)
            print(f"    Logarithmic search found: {discovered_low}")
            print(f"[+] Total discovered parameters on {endpoint}: {len(all_params)}")
        return list(all_params)

# ------------------------------------------------------------
#  Main script
# ------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Web Endpoint & Parameter Enumeration Tool")
    parser.add_argument("url", help="Base URL of the target (e.g., http://example.com)")
    parser.add_argument("--crawl-depth", type=int, default=2, help="Depth for crawling (default 2)")
    parser.add_argument("--method", choices=['GET', 'POST'], default='GET', help="HTTP method to use")
    parser.add_argument("--speed", choices=['fast', 'medium', 'slow'], default='medium', help="Scan speed")
    parser.add_argument("--accuracy", choices=['low', 'medium', 'high'], default='medium', help="Detection accuracy (affects threshold)")
    parser.add_argument("--noise", choices=['low', 'medium', 'high'], default='low', help="Noise level (random delays, UA rotation)")
    parser.add_argument("--wordlist", help="File containing parameter names (one per line)")
    parser.add_argument("--output", help="Save discovered endpoints and parameters to JSON file")
    args = parser.parse_args()

    base_url = args.url.rstrip('/')
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; EnumTool/1.0)'})

    # 1. Enumerate endpoints
    enumerator = EndpointEnumerator(base_url, session, depth=args.crawl_depth)
    endpoints = enumerator.run()

    # 2. Discover parameters
    discoverer = ParameterDiscoverer(session, base_url, method=args.method,
                                     speed=args.speed, accuracy=args.accuracy, noise=args.noise)
    discovered_params = discoverer.discover_parameters(endpoints, wordlist_file=args.wordlist)

    # 3. Output results
    result = {
        "target": base_url,
        "endpoints": endpoints,
        "parameters": discovered_params
    }
    print("\n=== Summary ===")
    print(f"Endpoints found: {len(endpoints)}")
    for ep in endpoints[:20]:  # show first 20
        print(f"  {ep}")
    if len(endpoints) > 20:
        print(f"  ... and {len(endpoints)-20} more")
    print(f"\nParameters discovered: {len(discovered_params)}")
    for p in discovered_params[:20]:
        print(f"  {p}")
    if len(discovered_params) > 20:
        print(f"  ... and {len(discovered_params)-20} more")

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()

