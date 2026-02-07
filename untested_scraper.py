import re
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup
from collections import defaultdict, Counter
# CHANGES MADE SINCE LAST PUSH:
# 1. created a separate container for visited urls
# 2. made a separate function for domain checking 
# 3. made a separate function to weed out infinite traps
# 4. cleaned up extract_text_from_html
# 5. meet low-information detection requirement with is_low_info(_)

# REASON FOR CHANGES:
# 1. seemed easier idk + doublechecking
# (2 & 3): I didn't like how complicated and bulky the is_valid()
#          function had become, so I wanted to clean it up.
#          I didn't really add much new here, just made a separate function. 
# 4. I was looking it up and found a cleaner/easier way to do it lol.
# 5. last update I mentioned that we should implement size checking
#    but also its a requirement that we try to filter out low info stuff

# Simple statistics containers
UNIQUE_PAGES = set()
VISITED_URLS = set()
PAGE_WORD_COUNTS = {}
ALL_WORDS_COUNTER = Counter()
ALL_SUBDOMAINS = defaultdict(set)
LONGEST_PAGE = {"url": "", "word_count": 0}
URL_PATTERN_COUNTER = defaultdict(int)

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

KNOWN_TRAP_PATTERNS = [
    r'.*/events/.*',
    r'.*/event/.*',
    r'.*/calendar/.*',
    r'.*/ical/.*',
    r'.*/~eppstein/pix/.*',
    r'.*doku\.php.*',
    r'.*/doku\.php\?.*',
    r'.*/wiki/doku\.php\?.*',
    #r'.*/~dechter/.*', # unsure abt this one
]

KNOWN_TRAP_DOMAINS = {
    'wics.ics.uci.edu',
    'ngs.ics.uci.edu',
    'isg.ics.uci.edu',
    'grape.ics.uci.edu'
}

MIN_CONTENT_WORDS = 100
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB i saw someone recommend in discord


def normalize_url(url):
    """URL normalization (remove fragment and normalize)"""
    url, _ = urldefrag(url)
    url = url.lower()
    # Remove trailing slash
    if url.endswith('/'):
        url = url[:-1]
    return url

def is_valid_domain(domain):
    if ':' in domain: # port removal maybe not necessary
        domain = domain.split(':')[0]
    
    allowed_domains = ['ics.uci.edu', 'cs.uci.edu', 'informatics.uci.edu', 'stat.uci.edu']
    
    if domain in allowed_domains:
        return True
    
    for allowed in allowed_domains:
        if domain.endswith('.' + allowed): # special handling cecs.uci.edu
            if allowed == 'cs.uci.edu':
                prefix = domain[:-10]  # remove "cs.uci.edu"
                if prefix and prefix.endswith('.'):
                    return True
            else:
                return True

def extract_text_from_html(html_content):
    """Extract clean text from HTML using stripped_strings"""
    if not html_content:
        return ""   
    try:
        soup_html_content = BeautifulSoup(html_content, 'html.parser')
        
        for element in soup_html_content(["script", "style"]):
            element.decompose()
        text = ' '.join(soup_html_content.stripped_strings) # gets text and handles whitespace
        
        return text
    except:
        return ""

def tokenize_text(text):
    """basic tokenizing"""
    if not text:
        return []
    
    tokens = []
    text = text.lower()
    
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
    
    # Filter out stop words
    filtered_tokens = []
    for token in tokens:
        if token not in STOP_WORDS and len(token) > 1 and not (token.isdigit()):
            filtered_tokens.append(token)
    
    return filtered_tokens

def is_low_information_page(text, html_content):
    """
    check if page has low information value
    returns True for pages with too little text or poor text-to-HTML ratio
    """
    if not text:
        return True
    
    words = text.split()
    
    # too few words (less than minimum required)
    if len(words) < MIN_CONTENT_WORDS:
        return True

    # text-to-HTML ratio (we're picking 5%) but if we need to can change
    text_length = len(text)
    html_length = len(html_content) if html_content else 0
    
    if html_length > 0 and text_length / html_length < 0.05:
        return True
    
    return False

def is_infinite_trap_url(url):
    """
    Detect infinite traps via URL patterns (pagination, session IDs, etc.)
    Returns True if URL looks like an infinite trap
    # https://support.archive-it.org/hc/en-us/articles/208332963-Modify-crawl-scope-with-a-Regular-Expression 
    # ^.*(/misc|/sites|/all|/themes|/modules|/profiles|/css|/field|/node|/theme){3}.*$
    """
    parsed = urlparse(url)
    
    # avoid auto-generated pages
    # should already be avoiding by blocking out calendars, etc
    # but just in case we missed something
    if parsed.query:
        normalized = re.sub(r'\d+', '#', url.lower()) # normalize URL by replacing numbers with #
        URL_PATTERN_COUNTER[normalized] += 1
        
        if URL_PATTERN_COUNTER[normalized] > 20: # subjective 
            return True
        
        # Check for session IDs and other trap parameters
        trap_params = ['sessionid=', 'sid=', 'phpsessid=', 'jsessionid=']
        query_lower = parsed.query.lower()
        if any(param in query_lower for param in trap_params):
            return True
    
    # Check for too many slashes (deep nesting)
    if url.count('/') > 15:
        return True
    
    # Check for very long URLs
    if len(url) > 500:
        return True
    
    return False


def update_statistics(url, text):
    """Update statistics for crawled page"""
    global LONGEST_PAGE
    
    normalized_url = normalize_url(url)
    if normalized_url in UNIQUE_PAGES: # Skip if already processed
        return
    UNIQUE_PAGES.add(normalized_url)
    
    # count words + update (simple word count for page length)
    word_count = len(text.split())
    PAGE_WORD_COUNTS[normalized_url] = word_count
    
    if word_count > LONGEST_PAGE["word_count"]:
        LONGEST_PAGE = {"url": normalized_url, "word_count": word_count}
    
    tokens = tokenize_text(text)
    for token in tokens:
        ALL_WORDS_COUNTER[token] += 1 #global word ocunter
    
    # tracking subdomains
    parsed = urlparse(normalized_url)
    domain = parsed.netloc.lower()
    ALL_SUBDOMAINS[domain].add(normalized_url)

def extract_next_links(url, resp):
    """
    Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    """
    links = []
    if resp.status != 200: # 200 is OK, you got the page
        return links
    
    if not resp.raw_response or not resp.raw_response.content:
        return links
    
    try:
        content = resp.raw_response.content
        content_size = len(content)
        if content_size > MAX_FILE_SIZE:
            return links

        # REFERENCE: https://www.geeksforgeeks.org/python/beautifulsoup-scraping-paragraphs-from-html/
        html_parse = BeautifulSoup(resp.raw_response.content, 'html.parser')
        
        for a_tag in html_parse.find_all('a', href=True): # extracting all the URLs found within a page's <a> tags (anchor tags)
            href = a_tag['href']
            # REFERENCE: https://www.crummy.com/software/BeautifulSoup/bs4/doc/ 
            
            absolute_url = urljoin(url, href) # handle relative URLs
            normalized_url = normalize_url(absolute_url) # normalize URL
            if normalized_url in VISITED_URLS:
                continue
            links.append(normalized_url)
                            
    except Exception as e:
        print(f"Error extracting links from {url}: {e}")
    
    return links

def is_valid(url):
    """Check if URL should be crawled"""
    try:
        parsed = urlparse(url)
        
        if parsed.scheme not in {"http", "https"}:
            return False
        
        domain = parsed.netloc.lower()
        if not domain:
            return False
        
        if domain in KNOWN_TRAP_DOMAINS:
            return False
        
        if not is_valid_domain(domain):
            return False
        
        url_lower = url.lower()

        for pattern in KNOWN_TRAP_PATTERNS:
            if re.match(pattern, url_lower, re.I) or re.search(pattern, url_lower, re.I):
                return False

        if is_infinite_trap_url(url):
            return False
        
        string_check = [
            '/events/',
            '/event/',
            '/calendar/',
            'doku.php',
            #'/~dechter/',
        ]
        for indicator in string_check: # backup  string check
            if indicator in url_lower:
                return False
        
        # All default excep added:  pps, mpg
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4|pps|mpg"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|pps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|mpg|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())
        
    except Exception as e:
        print(f"Error in is_valid for {url}: {e}")
        return False

def generate_report():
    """Generate the required report"""
    report_lines = []
    
    # 1. Unique pages count
    report_lines.append(f"1. Unique pages found: {len(UNIQUE_PAGES)}")
    report_lines.append("")
    
    # 2. Longest page
    report_lines.append(f"2. Longest page in terms of number of words:")
    report_lines.append(f"   URL: {LONGEST_PAGE['url']}")
    report_lines.append(f"   Word count: {LONGEST_PAGE['word_count']}")
    report_lines.append("")
    
    # 3. 50 most common words
    report_lines.append("3. 50 most common words in the entire set of pages (ignoring English stop words):")
    
    # Get top 50 words
    for i, (word, count) in enumerate(ALL_WORDS_COUNTER.most_common(50), 1):
        report_lines.append(f"   {i:2d}. {word}: {count}")
    report_lines.append("")
    
    # 4. Subdomains in uci.edu domain
    report_lines.append("4. Subdomains found in the uci.edu domain:")
    
    # Filter and sort subdomains
    uci_subdomains = {}
    for subdomain, urls in ALL_SUBDOMAINS.items():
        if subdomain.endswith('.uci.edu'):
            uci_subdomains[subdomain] = len(urls)
    
    for subdomain in sorted(uci_subdomains.keys()):
        report_lines.append(f"   {subdomain}, {uci_subdomains[subdomain]}")
    
    return "\n".join(report_lines)

def save_report(filename="crawler_report.txt"):
    """Save report to file"""
    report = generate_report()
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Report saved to {filename}")

import atexit # using for debugging rn but get rid of for final
page_counter = 0

def scraper(url, resp):
    global page_counter
    page_counter += 1
    if page_counter % 100 == 0:
        print(f"DEBUG: Processed {page_counter} pages, unique so far: {len(UNIQUE_PAGES)}")
    
    normalized_url = normalize_url(url)
    if normalized_url in VISITED_URLS:
        return []
    VISITED_URLS.add(normalized_url)
    
    if resp.status == 200 and resp.raw_response and resp.raw_response.content:
        try:           
            # Extract text from HTML
            html_content = resp.raw_response.content
            text = extract_text_from_html(html_content)

            if is_low_information_page(text, html_content):
                return []
            
            update_statistics(url, text)
            
        except Exception as e:
            print(f"Error processing {url}: {e}")

    links = extract_next_links(url, resp)
    
    # Return only valid links
    valid_links = []
    for link in links:
        if is_valid(link):
            valid_links.append(link)
    
    return valid_links
atexit.register(lambda: print(f"\nFinal count: Processed {page_counter} pages, found {len(UNIQUE_PAGES)} unique URLs"))
atexit.register(save_report)
