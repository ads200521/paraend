# Web Enumeration Tool

A powerful web reconnaissance and endpoint discovery tool designed for security researchers, penetration testers, and bug bounty hunters.

This tool performs intelligent endpoint enumeration and parameter discovery using a combination of crawling, archival analysis, heuristic detection, and logarithmic batch searching.

---

## Features

### Endpoint Enumeration
- Recursive web crawling
- Wayback Machine URL collection
- Discovery of common files and directories
- JavaScript endpoint extraction
- Smart URL deduplication

### Hybrid Parameter Discovery
- High-probability heuristic parameter detection
- Logarithmic batch search for low-probability parameters
- Adaptive testing strategies
- Automatic parameter prioritization

### Adaptive Learning Engine
- Learns reusable parameters across endpoints
- Improves discovery accuracy during runtime
- Reduces redundant requests

### Configurable Profiles
Choose between:
- Fast Scan
- Balanced Scan
- Deep Enumeration

Profiles control:
- Request speed
- Noise level
- Accuracy
- Aggressiveness

---

## Architecture

```text
Target URL
    ↓
Crawler / Wayback Collection
    ↓
Endpoint Extraction
    ↓
Parameter Discovery Engine
    ↓
Heuristic + Batch Analysis
    ↓
Adaptive Learning System
    ↓
Results Output
```

---

## Installation

### Clone Repository

```bash
git clone https://github.com/your-username/web-enumeration-tool.git
cd web-enumeration-tool
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Usage

### Basic Scan

```bash
python main.py -u https://target.com
```

### Deep Enumeration

```bash
python main.py -u https://target.com --profile deep
```

### Custom Threads

```bash
python main.py -u https://target.com -t 50
```

---

## Command Line Options

| Option | Description |
|---|---|
| `-u` | Target URL |
| `-t` | Number of threads |
| `--profile` | Scan profile |
| `--wayback` | Enable Wayback collection |
| `--crawl-depth` | Set crawling depth |
| `--output` | Output file |

---

## Example Output

```text
[+] Endpoint Found: /api/login
[+] Endpoint Found: /admin/dashboard
[+] Parameter Detected: user_id
[+] Parameter Detected: redirect_url
```

---

## Use Cases

- Web application reconnaissance
- Bug bounty automation
- Hidden endpoint discovery
- Parameter fuzzing preparation
- Attack surface mapping

---

## Technologies Used

- Python
- Requests
- BeautifulSoup
- AsyncIO
- Wayback Machine APIs

---

## Future Improvements

- Headless browser support
- GraphQL endpoint detection
- AI-assisted parameter prediction
- Distributed scanning support
- Custom wordlist generation

---

## Legal Disclaimer

This tool is intended for authorized security testing and educational purposes only.

Do not use against systems without proper authorization.

---

## Author

Aditya Jain
