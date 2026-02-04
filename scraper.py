import re
from urllib.parse import urlparse, urljoin, urldefrag, urllib.request
from bs4 import BeautifulSoup
from lxml import html, etree
import hashlib
from collections import defaultdict, Counter

# statistics containers
unique_urls = set()
page_word_counts = {}
all_words_counter = Counter()
subdomains = defaultdict(set)
longest_page = {"url": "", "word_count": 0}

STOP_WORDS = set(["a", "about", "above", "after", "again", "against", "all",
            "am", "an", "and", "any", "are", "aren", "t", "as", "at", # separate 't' for tokenizing? UNSURE. 
            "be", "because", "been", "before", "being", "below", "between",
            "both", "but", "by", "can", "not", "cannot", "could",
            "couldn", "did", "didn", "do", "does", "doesn", "doing",
            "don", "down", "during", "each", "few", "for", "from",
            "further", "had", "hadn", "has", "hasn", "have", "haven",
            "having", "he", "d", "ll", "s", "her", "here", "hers",
            "herself", "him", "himself", "his", "how", "i", "if", "in",
            "into", "is", "isn", "it", "its", "itself", "let", "me",
            "more", "most", "mustn", "my", "myself", "no", "nor", "of",
            "off", "on", "once", "only", "or", "other", "ought",
            "our", "ours", "ourselves", "out", "over", "own", "same",
            "shan", "she", "should", "shouldn", "so", "some", "such",
            "than", "that", "the", "their", "theirs", "them", "themselves",
            "then", "there", "these", "they", "this", "those",
            "through", "to", "too", "under", "until", "up", "very",
            "was", "wasn", "we", "what", "when", "where", "which",
            "while", "who", "whom", "why", "with", "won", "would",
            "wouldn", "you", "your", "yours", "yourself", "yourselves"])
            # if x in set ([]) --> O(1) time complexity

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    links = []
    if resp.status != 200: # 200 is OK, you got the page
        return links

    if (600 <= resp.status <= 606): # when status is not 200, you can check the error here, if needed.
        return (f"ERROR: {resp.status}")
    
    # resp.raw_response: this is where the page actually is
    if not resp.raw_response.content:
        return links
    
    # parsing the html file
    # BeautifulSoup recommended in assignment instructions
    # INSTRUCTIONS HOW TO USE: https://www.geeksforgeeks.org/python/beautifulsoup-scraping-paragraphs-from-html/
    try:
       html_parse = BeautifulSoup(content, 'html.parser') 
    except:
        return links
    
    text = html_parse.get_text(separator=' ', strip=True)
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    words = [w for w in words if w not in STOP_WORDS]
    
    # statistics
    defrag_url = urldefrag(url)[0]
    unique_urls.add(defrag_url)
    word_count = len(words)
    page_word_counts[defrag_url] = word_count
    
    if word_count > longest_page["word_count"]:
        longest_page["url"] = defrag_url
        longest_page["word_count"] = word_count
    
    for word in words:
        all_words_counter[word] += 1
    
    parsed = urlparse(defrag_url)
    if parsed.netloc.endswith('.uci.edu'):
        subdomains[parsed.netloc].add(defrag_url)
    
    # link extracktion
    for link in html_parse.find_all('a', href=True):
        href = link['href']
        
        absolute_url = urljoin(url, href)
        defragmented = urldefrag(absolute_url)[0]
        links.append(defragmented)
    
    return links

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise

def print_stats():
    """Print current statistics"""
    print("\n" + "="*50)
    print("CRAWLER STATISTICS")
    print("="*50)
    print(f"Unique pages found: {len(unique_urls)}")
    print(f"Longest page: {longest_page['url']}")
    print(f"  Word count: {longest_page['word_count']}")
    
    print("\nTop 10 words:")
    for word, count in all_words_counter.most_common(10):
        print(f"  {word}: {count}")
    
    print("\nSubdomains found:")
    uci_subdomains = {}
    for subdomain, urls in subdomains.items():
        if subdomain.endswith('.uci.edu'):
            uci_subdomains[subdomain] = len(urls)
    
    for subdomain in sorted(uci_subdomains.keys()):
        print(f"  {subdomain}: {uci_subdomains[subdomain]} pages")
    
    return {
        'unique_pages': len(unique_urls),
        'longest_page': longest_page,
        'top_words': dict(all_words_counter.most_common(50)),
        'subdomains': uci_subdomains
    }