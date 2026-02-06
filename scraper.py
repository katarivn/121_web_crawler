import re
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup
from collections import defaultdict, Counter

#TODO:
# STILL NEED TO DO FULL RUNTHROUGH !! [*]
#   - I ran it for like 2+ hoursish and it found like 5000 unique urls
#     but then I had to leave for the quiz and when I came back the server had crashed
#
# ADD YOUR STUDENT ID TO CONFIG.INI
#
# Avoid very small or very large files [*] IMPORTANT
#
# Clean everything up, especially trap-checking logic 
#
# When finally done:
# go through and comment explaining everything so we're on the same page
# we're on the same page for the code review

# Simple statistics containers
UNIQUE_PAGES = set()
PAGE_WORD_COUNTS = {}
ALL_WORDS_COUNTER = Counter()
ALL_SUBDOMAINS = defaultdict(set)
LONGEST_PAGE = {"url": "", "word_count": 0}

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
    r'.*/~dechter/.*', # unsure abt this one
]

KNOWN_TRAP_DOMAINS = {
    'wics.ics.uci.edu',
    'ngs.ics.uci.edu',
    'isg.ics.uci.edu',
    'grape.ics.uci.edu'
}

def normalize_url(url):
    """URL normalization (remove fragment and normalize)"""
    url, _ = urldefrag(url)
    url = url.lower()
    # Remove trailing slash
    if url.endswith('/'):
        url = url[:-1]
    return url

def extract_text_from_html(html_content):
    """Extract text from HTML"""
    if not html_content:
        return ""
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # get text and clean up whitespace
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
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
    
    # Filter out stop words and very short tokens
    filtered_tokens = []
    for token in tokens:
        if token not in STOP_WORDS and len(token) > 1:
            filtered_tokens.append(token)
    
    return filtered_tokens

def count_words(text):
    """Count total words in text (for page length) w simple whitespace split"""
    if not text:
        return 0
    words = text.split()
    return len(words)

def update_statistics(url, text):
    """Update statistics for crawled page"""
    global LONGEST_PAGE
    
    normalized_url = normalize_url(url)
    if normalized_url in UNIQUE_PAGES: # Skip if already processed
        return
    UNIQUE_PAGES.add(normalized_url)
    
    # count words + update (simple word count for page length)
    word_count = count_words(text)
    PAGE_WORD_COUNTS[normalized_url] = word_count
    
    if word_count > LONGEST_PAGE["word_count"]:
        LONGEST_PAGE = {"url": normalized_url, "word_count": word_count}
    
    tokens = tokenize_text(text)
    for token in tokens:
        ALL_WORDS_COUNTER[token] += 1 #global word ocunter
    
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
        # REFERENCE: https://www.geeksforgeeks.org/python/beautifulsoup-scraping-paragraphs-from-html/
        html_parse = BeautifulSoup(resp.raw_response.content, 'html.parser')
        
        for a_tag in html_parse.find_all('a', href=True): # extracting all the URLs found within a page's <a> tags (anchor tags)
            href = a_tag['href']
            # REFERENCE: https://www.crummy.com/software/BeautifulSoup/bs4/doc/ 
            
            # Skip empty links and javascript links
            if not href or href.startswith(('javascript:', 'mailto:', 'tel:')):
                continue

            absolute_url = urljoin(url, href) # handle relative URLs
            normalized_url = normalize_url(absolute_url) # normalize URL
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
        
        allowed_domains = ['ics.uci.edu', 'cs.uci.edu', 'informatics.uci.edu', 'stat.uci.edu']
        is_allowed = False
        for allowed_domain in allowed_domains:
            if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                is_allowed = True
                break
        if not is_allowed:
            return False
        
        url_lower = url.lower()
        # POTENTIAL FIXME: trap detection
        # i think it works now but using both match and search
        # unsure if both are actually necessary
        for pattern in KNOWN_TRAP_PATTERNS:
            # Try re.match first (matches from start of string)
            if re.match(pattern, url_lower, re.I):
                return False
            # Also try re.search (matches anywhere in string)
            if re.search(pattern, url_lower, re.I):
                return False
        
        string_check = [
            '/events/',
            '/event/',
            '/calendar/',
            'doku.php',
            '/~dechter/',
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

        
        # TRAP AVOIDANCE:
        # Check for known trap patterns
        for pattern in KNOWN_TRAP_PATTERNS:
            if re.match(pattern, url, re.I):
                return False
        
        if path.count('/') > 10: # avoid deep paths (too many slashes)
            return False
        
        # Avoid URLs with query parameters that look like traps
        if parsed.query:
            query = parsed.query.lower()
            # Avoid pages with many query parameters
            if len(query.split('&')) > 5:
                return False
            # Avoid specific trap query patterns
            trap_queries = ['share=', 'replytocom=', 'action=', 'format=', 'download=', 'feed=']
            if any(trap in query for trap in trap_queries):
                return False
        
        # Additional trap avoidance: avoid URLs with specific patterns
        trap_patterns = [
            r'.*print=.*',
            r'.*pdf=.*',
            r'.*xml=.*',
            r'.*json=.*',
            r'.*rss=.*',
            r'.*atom=.*',
        ]
        full_url = url.lower()
        for pattern in trap_patterns:
            if re.match(pattern, full_url):
                return False
        
        return True
        
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
    
    links = extract_next_links(url, resp)
    
    if resp.status == 200 and resp.raw_response and resp.raw_response.content:
        try:           
            # TODO : check for file size 
            # not sure if this is the way to do it
            #content_size = len(content)
            #content = resp.raw_response.content

            # Extract text from HTML
            html_content = resp.raw_response.content
            text = extract_text_from_html(html_content)
            
            # Update statistics
            update_statistics(url, text)
            
        except Exception as e:
            print(f"Error processing {url}: {e}")
    
    # Return only valid links
    valid_links = []
    for link in links:
        if is_valid(link):
            valid_links.append(link)
    
    return valid_links
atexit.register(lambda: print(f"\nFinal count: Processed {page_counter} pages, found {len(UNIQUE_PAGES)} unique URLs"))
atexit.register(save_report)
