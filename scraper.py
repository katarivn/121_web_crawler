import re
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup
from collections import defaultdict, Counter
import atexit

# ==============================================================================
# Global Containers & Constants
# ==============================================================================

# Track unique pages found (for report)
UNIQUE_PAGES = set()

# Track all visited URLs to prevent loops (includes failed attempts)
VISITED_URLS = set()

# Statistics
PAGE_WORD_COUNTS = {}
ALL_WORDS_COUNTER = Counter()
ALL_SUBDOMAINS = defaultdict(set)
LONGEST_PAGE = {"url": "", "word_count": 0}

# Stop Words (English)
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", 
    "any", "are", "arent", "as", "at", "be", "because", "been", "before", "being", 
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldnt", 
    "did", "didnt", "do", "does", "doesnt", "doing", "dont", "down", "during", 
    "each", "few", "for", "from", "further", "had", "hadnt", "has", "hasnt", 
    "have", "havent", "having", "he", "hed", "hell", "hes", "her", "here", 
    "heres", "hers", "herself", "him", "himself", "his", "how", "hows", "i", 
    "id", "ill", "im", "ive", "if", "in", "into", "is", "isnt", "it", "its", 
    "itself", "lets", "me", "more", "most", "mustnt", "my", "myself", 
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", 
    "our", "ours", "ourselves", "out", "over", "own", "same", "shant", "she", 
    "shed", "shell", "shes", "should", "shouldnt", "so", "some", "such", "than", 
    "that", "thats", "the", "their", "theirs", "them", "themselves", "then", 
    "there", "theres", "these", "they", "theyd", "theyll", "theyre", "theyve", 
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", 
    "wasnt", "we", "wed", "well", "were", "weve", "were", "werent", "what", 
    "whats", "when", "whens", "where", "wheres", "which", "while", "who", "whos", 
    "whom", "why", "whys", "with", "wont", "would", "wouldnt", "you", "youd", 
    "youll", "youre", "youve", "your", "yours", "yourself", "yourselves"
}

# Trap Patterns to Avoid
KNOWN_TRAP_PATTERNS = [
    r'.*/events/.*',
    r'.*/event/.*',
    r'.*/calendar/.*',
    r'.*/ical/.*',
    r'.*/~eppstein/pix/.*',
]

# Domains to Avoid (known traps)
KNOWN_TRAP_DOMAINS = {
    'isg.ics.uci.edu',
    'grape.ics.uci.edu'
}

# Thresholds
MIN_CONTENT_WORDS = 50
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit

# Page counter for logging
page_counter = 0


# ==============================================================================
# Helper Functions
# ==============================================================================

def normalize_url(url):
    """Normalize URL: remove fragments, convert to lower case, remove trailing slash."""
    url, _ = urldefrag(url)
    url = url.lower()
    if url.endswith('/'):
        url = url[:-1]
    return url

def is_valid_domain(domain):
    """Check if the domain is within the allowed scope."""
    if ':' in domain: 
        domain = domain.split(':')[0]
    
    allowed_domains = ['ics.uci.edu', 'cs.uci.edu', 'informatics.uci.edu', 'stat.uci.edu']
    
    if domain in allowed_domains:
        return True
    
    for allowed in allowed_domains:
        if domain.endswith('.' + allowed):
            return True
        
    return False

def extract_text_from_html(html_content):
    """Extract visible text from HTML content, removing scripts and styles."""
    if not html_content:
        return ""   
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for element in soup(["script", "style"]):
            element.decompose()
            
        # Get text and clean up whitespace
        text = ' '.join(soup.stripped_strings)
        return text
    except:
        return ""

def tokenize_text(text):
    """Tokenize text: lower case, alphanumeric check, remove stop words."""
    if not text:
        return []
    
    tokens = []
    text = text.lower()
    
    # Simple tokenization
    lines = text.split('\n')
    for line in lines:
        line_words = line.split()
        for word in line_words:
            current_token = ''
            for char in word:
                if char.isalnum() and char.isascii():
                    current_token += char
                else:
                    if current_token:
                        tokens.append(current_token)
                        current_token = ''
            if current_token:
                tokens.append(current_token)
    
    # Filter tokens
    filtered_tokens = []
    for token in tokens:
        if token not in STOP_WORDS and len(token) > 1 and not (token.isdigit()):
            filtered_tokens.append(token)
    
    return filtered_tokens

def is_low_information_page(text, html_content):
    """Check if the page has low information value (too few words or low text/html ratio)."""
    if not text:
        return True
    
    words = text.split()
    
    # Check minimum word count
    if len(words) < MIN_CONTENT_WORDS:
        return True

    # Check text-to-HTML ratio (threshold: 5%)
    text_length = len(text)
    html_length = len(html_content) if html_content else 0

    if html_length > 0 and text_length / html_length < 0.05:
        return True
    
    return False

def is_infinite_trap_url(url):
    """Detect potential infinite traps based on URL patterns."""
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    
    # DokuWiki traps
    if 'doku.php' in path_lower and parsed.query:
        query_lower = parsed.query.lower()
        wiki_trap_params = ['do=', 'rev=', 'rev2', 'idx=', 'difftype=']
        if any(param in query_lower for param in wiki_trap_params):
            return True
            
    # Deep nesting check
    if url.count('/') > 25:
        return True
    
    return False

def update_statistics(url, text):
    """Update global statistics with data from the current page."""
    global LONGEST_PAGE
    
    normalized_url = normalize_url(url)
    if normalized_url in UNIQUE_PAGES:
        return
    UNIQUE_PAGES.add(normalized_url)
    
    # Count words
    word_count = len(text.split())
    PAGE_WORD_COUNTS[normalized_url] = word_count
    
    # Check for longest page
    if word_count > LONGEST_PAGE["word_count"]:
        LONGEST_PAGE = {"url": normalized_url, "word_count": word_count}
    
    # Update word frequency
    tokens = tokenize_text(text)
    for token in tokens:
        ALL_WORDS_COUNTER[token] += 1
    
    # Update subdomains
    parsed = urlparse(normalized_url)
    domain = parsed.netloc.lower()
    ALL_SUBDOMAINS[domain].add(normalized_url)

def extract_next_links(url, resp):
    """Extract hyperlinks from the response content."""
    links = []
    
    # Basic validation before parsing
    if resp.status != 200 or not resp.raw_response or not resp.raw_response.content:
        return links
    
    try:
        # Note: File size check is done in scraper() now for optimization
        
        html_parse = BeautifulSoup(resp.raw_response.content, 'html.parser')
        
        for a_tag in html_parse.find_all('a', href=True):
            href = a_tag['href']
            
            # Resolve relative URLs
            absolute_url = urljoin(url, href)
            normalized_url = normalize_url(absolute_url)
            
            links.append(normalized_url)
                            
    except Exception as e:
        print(f"Error extracting links from {url}: {e}")
    
    return links

def is_valid(url):
    """Decide whether to crawl this URL."""
    try:
        parsed = urlparse(url)
        
        if parsed.scheme not in {"http", "https"}:
            return False
        
        domain = parsed.netloc.lower()
        if not domain:
            return False
        
        # Check forbidden domains
        if domain in KNOWN_TRAP_DOMAINS:
            return False
        
        # Check allowed domains
        if not is_valid_domain(domain):
            return False
        
        url_lower = url.lower()

        # Check known trap regex patterns
        for pattern in KNOWN_TRAP_PATTERNS:
            if re.match(pattern, url_lower, re.I) or re.search(pattern, url_lower, re.I):
                return False

        # Check logic-based infinite traps
        if is_infinite_trap_url(url):
            return False
        
        # Check specific string indicators for traps
        string_check = [
            '/events/',
            '/event/',
            '/calendar/',
        ]
        for indicator in string_check:
            if indicator in url_lower:
                return False
        
        # Check file extensions to avoid
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4|mpg|pps"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())
        
    except Exception as e:
        print(f"Error in is_valid for {url}: {e}")
        return False

# ==============================================================================
# Reporting Functions
# ==============================================================================

def generate_report():
    """Generate the formatted report string."""
    report_lines = []
    
    report_lines.append(f"1. Unique pages found: {len(UNIQUE_PAGES)}")
    report_lines.append("")
    
    report_lines.append(f"2. Longest page in terms of number of words:")
    report_lines.append(f"   URL: {LONGEST_PAGE['url']}")
    report_lines.append(f"   Word count: {LONGEST_PAGE['word_count']}")
    report_lines.append("")
    
    report_lines.append("3. 50 most common words in the entire set of pages (ignoring English stop words):")
    for i, (word, count) in enumerate(ALL_WORDS_COUNTER.most_common(50), 1):
        report_lines.append(f"   {i:2d}. {word}: {count}")
    report_lines.append("")
    
    report_lines.append("4. Subdomains found in the uci.edu domain:")
    uci_subdomains = {}
    for subdomain, urls in ALL_SUBDOMAINS.items():
        if subdomain.endswith('.uci.edu'):
            uci_subdomains[subdomain] = len(urls)
    
    for subdomain in sorted(uci_subdomains.keys()):
        report_lines.append(f"   {subdomain}, {uci_subdomains[subdomain]}")
    
    return "\n".join(report_lines)

def save_report(filename="crawler_report.txt"):
    """Save the generated report to a file."""
    report = generate_report()
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Report saved to {filename}")

# Register exit handlers to save report on termination
atexit.register(lambda: print(f"\nFinal count: Processed {page_counter} pages, found {len(UNIQUE_PAGES)} unique URLs"))
atexit.register(save_report)


# ==============================================================================
# Main Scraper Function
# ==============================================================================

def scraper(url, resp):
    global page_counter
    page_counter += 1
    
    # [Optimization] Periodic save to prevent data loss
    if page_counter % 500 == 0:
        print(f"DEBUG: Saving periodic report... (Count: {page_counter})")
        save_report()

    if page_counter % 100 == 0:
        print(f"DEBUG: Processed {page_counter} pages, unique so far: {len(UNIQUE_PAGES)}")
    
    # 1. Check if URL has already been visited
    normalized_url = normalize_url(url)
    if normalized_url in VISITED_URLS:
        return []
    VISITED_URLS.add(normalized_url)
    
    # 2. Check response status and content validity
    if resp.status != 200 or not resp.raw_response or not resp.raw_response.content:
        return []

    # [Optimization] Check file size BEFORE parsing to save memory
    if len(resp.raw_response.content) > MAX_FILE_SIZE:
        # print(f"Skipping large file: {url}")
        return []

    try:           
        # 3. Extract text and analyze
        html_content = resp.raw_response.content
        text = extract_text_from_html(html_content)

        # 4. Low information check
        if is_low_information_page(text, html_content):
            return []
        
        # 5. Update statistics
        update_statistics(url, text)
        
    except Exception as e:
        print(f"Error processing {url}: {e}")

    # 6. Extract links
    links = extract_next_links(url, resp)
    
    # 7. Filter valid links
    valid_links = []
    for link in links:
        if is_valid(link):
            valid_links.append(link)
    
    return valid_links
