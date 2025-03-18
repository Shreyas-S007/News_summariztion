import requests
import os
import json
from bs4 import BeautifulSoup
from gtts import gTTS
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from dotenv import load_dotenv
from googletrans import Translator
import google.generativeai as genai
import uuid
from collections import Counter
import tempfile

# Load environment variables
load_dotenv()

# Initialize sentiment analyzer and translator
analyzer = SentimentIntensityAnalyzer()
translator = Translator()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')


def fetch_news(company_name):
    """Fetch news articles from NewsAPI"""
    api_key = os.getenv("NEWS_API_KEY")
    url = f"https://newsapi.org/v2/everything?q={company_name}&language=en&apiKey={api_key}"

    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        processed_articles = []

        # Limit to 4 articles as requested
        for art in articles[:4]:
            content = scrape_article(art["url"])
            summary = generate_summary(content, company_name)
            topics = extract_topics(art["title"], content, company_name)
            sentiment = analyze_sentiment(content)

            processed_articles.append({
                "Title": art["title"],
                "url": art["url"],
                "content": content,
                "Summary": summary,
                "Sentiment": sentiment,
                "Topics": topics,
                "source": art.get("source", {}).get("name", "Unknown Source")
            })

        # Generate comparative analysis after processing all articles
        comparative_analysis = generate_comparative_analysis(processed_articles, company_name)

        # Format the output according to the requested structure
        formatted_output = {
            "Company": company_name,
            "Articles": processed_articles,
            "Comparative Sentiment Score": comparative_analysis
        }

        return formatted_output
    else:
        return {"Company": company_name, "Articles": [], "Comparative Sentiment Score": {}}


def generate_comparative_analysis(articles, company_name):
    """Generate comparative analysis of news coverage"""
    if not articles or len(articles) < 2:
        return {"error": "Not enough articles for comparative analysis"}

    # Extract data for structured analysis
    sentiment_counts = Counter()
    all_topics = []

    for article in articles:
        sentiment_counts[article["Sentiment"]] += 1
        for topic in article["Topics"]:
            all_topics.append(topic)

    # Calculate sentiment distribution
    sentiment_distribution = {k: v for k, v in sentiment_counts.items()}

    # Generate detailed comparison between articles
    coverage_differences = generate_detailed_comparisons(articles)

    # Find topic overlaps
    topic_overlap = calculate_topic_overlap(articles)

    # Final sentiment analysis
    final_sentiment = determine_final_sentiment(sentiment_counts, company_name)

    # Create a structured analysis object
    analysis = {
        "Sentiment Distribution": sentiment_distribution,
        "Coverage Differences": coverage_differences,
        "Topic Overlap": topic_overlap,
        "Final Sentiment Analysis": final_sentiment
    }

    return analysis


def generate_detailed_comparisons(articles):
    """Generate detailed comparisons between each pair of articles"""
    comparisons = []

    # Compare each pair of articles for a more comprehensive analysis
    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            article1 = articles[i]
            article2 = articles[j]

            try:
                # Use Gemini to generate detailed comparisons
                prompt = f"""
                Create a detailed comparison between these two news articles about the same company:

                ARTICLE {i + 1}:
                Title: {article1['Title']}
                Summary: {article1['Summary']}
                Sentiment: {article1['Sentiment']}
                Topics: {', '.join(article1['Topics'])}

                ARTICLE {j + 1}:
                Title: {article2['Title']}
                Summary: {article2['Summary']}
                Sentiment: {article2['Sentiment']}
                Topics: {', '.join(article2['Topics'])}

                Please provide TWO detailed comparison aspects:

                1. A clear comparison of the content focus and angle between these articles
                2. An analysis of the potential market/business impact these different perspectives might have

                Format exactly like this example:
                "Comparison": "Article 1 highlights Tesla's strong sales, while Article 2 discusses regulatory issues.",
                "Impact": "The first article boosts confidence in Tesla's market growth, while the second raises concerns about future regulatory hurdles."

                Do not include labels like "1." or "Comparison:" in your response text itself.
                Just provide the comparative text directly.
                """

                response = model.generate_content(prompt)
                content = response.text.strip()

                # Parse the response to extract comparison and impact
                parts = content.split('\n')

                comparison = ""
                impact = ""

                for part in parts:
                    if part.strip().startswith('"Comparison":'):
                        comparison = part.split(':', 1)[1].strip().strip('"').strip(',').strip('"').strip()
                    elif part.strip().startswith('"Impact":'):
                        impact = part.split(':', 1)[1].strip().strip('"').strip(',').strip('"').strip()

                # If parsing failed, use a fallback method
                if not comparison or not impact:
                    # Simple fallback
                    comparison = f"Article {i + 1} focuses on {article1['Topics'][0] if article1['Topics'] else 'general news'}, while Article {j + 1} covers {article2['Topics'][0] if article2['Topics'] else 'other aspects'}."
                    impact = f"Article {i + 1} presents a {article1['Sentiment'].lower()} view that might {get_impact_by_sentiment(article1['Sentiment'])}, while Article {j + 1}'s {article2['Sentiment'].lower()} angle could {get_impact_by_sentiment(article2['Sentiment'])}."

                comparisons.append({
                    "Comparison": comparison,
                    "Impact": impact,
                    "Articles": f"{i + 1} and {j + 1}"  # Include article numbers for reference
                })

            except Exception as e:
                print(f"Detailed Comparison Error: {e}")
                fallback_comparison = {
                    "Comparison": f"Article {i + 1} focuses on {article1['Topics'][0] if article1['Topics'] else 'general news'}, while Article {j + 1} covers {article2['Topics'][0] if article2['Topics'] else 'other aspects'}.",
                    "Impact": f"Article {i + 1} presents a {article1['Sentiment'].lower()} view that might {get_impact_by_sentiment(article1['Sentiment'])}, while Article {j + 1}'s {article2['Sentiment'].lower()} angle could {get_impact_by_sentiment(article2['Sentiment'])}.",
                    "Articles": f"{i + 1} and {j + 1}"
                }
                comparisons.append(fallback_comparison)

    return comparisons


def get_impact_by_sentiment(sentiment):
    """Generate an impact statement based on sentiment"""
    if sentiment == "Positive":
        return "boost investor confidence"
    elif sentiment == "Negative":
        return "raise concerns among stakeholders"
    else:
        return "have a neutral effect on market perception"


def calculate_topic_overlap(articles):
    """Calculate common and unique topics between articles"""
    if len(articles) < 2:
        return {"Common Topics": [], "Unique Topics By Article": {}}

    # Extract all topics
    all_topics = []
    article_topics = {}

    for i, article in enumerate(articles):
        article_topics[i + 1] = article["Topics"]
        all_topics.extend(article["Topics"])

    # Count occurrences
    topic_counts = Counter(all_topics)

    # Common topics appear in multiple articles
    common_topics = [topic for topic, count in topic_counts.items() if count > 1]

    # Build unique topics by article
    unique_topics = {}
    for i, topics in article_topics.items():
        article_unique_topics = []
        for topic in topics:
            # Only include if it's unique to this article
            if topic_counts[topic] == 1:
                article_unique_topics.append(topic)

        if article_unique_topics:
            unique_topics[f"Unique Topics in Article {i}"] = article_unique_topics

    return {
        "Common Topics": common_topics,
        "Unique Topics By Article": unique_topics
    }


def determine_final_sentiment(sentiment_counts, company_name):
    """Generate a final sentiment analysis statement"""
    total = sum(sentiment_counts.values())

    if total == 0:
        return f"No sentiment data available for {company_name}."

    # Calculate percentages
    positive_percent = (sentiment_counts.get("Positive", 0) / total) * 100
    negative_percent = (sentiment_counts.get("Negative", 0) / total) * 100
    neutral_percent = (sentiment_counts.get("Neutral", 0) / total) * 100

    # Determine overall sentiment
    if positive_percent > max(negative_percent, neutral_percent):
        overall = "mostly positive"
        impact = "Potential stock growth expected"
    elif negative_percent > max(positive_percent, neutral_percent):
        overall = "mostly negative"
        impact = "Potential stock decline expected"
    else:
        overall = "mixed or neutral"
        impact = "Market reaction may be muted"

    return f"{company_name}'s latest news coverage is {overall}. {impact}."


def scrape_article(url):
    """Scrape news article content using BeautifulSoup"""
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = soup.find_all("p")
        content = " ".join([para.get_text() for para in paragraphs])
        return content[:3000]  # Limit content length but allow enough for good summarization
    except:
        return "Content unavailable"


def generate_summary(content, company_name):
    """Generate a concise summary using Gemini API"""
    if content == "Content unavailable" or len(content) < 100:
        return "Summary unavailable"

    try:
        prompt = f"""
        Summarize the following news article about {company_name} in 2-3 concise sentences:

        {content[:2000]}
        """

        response = model.generate_content(prompt)
        summary = response.text.strip()

        # Limit summary length
        if len(summary) > 300:
            summary = summary[:297] + "..."

        return summary
    except Exception as e:
        print(f"Summary Generation Error: {e}")
        # Fallback to first 200 chars if Gemini fails
        return content[:200] + "..." if len(content) > 200 else content


def extract_topics(title, content, company_name):
    """Extract multiple topics for an article using Gemini API"""
    try:
        prompt = f"""
        List the 2-3 main topics of this news article about {company_name}.
        Respond with ONLY a JSON array of strings (topic names only). 
        Choose from: Electric Vehicles, Stock Market, Innovation, Regulations, 
        Autonomous Vehicles, Financial Results, Product Launch, Leadership, 
        Partnerships, Competition, Sustainability, Manufacturing, Global Markets.

        Example response: ["Electric Vehicles", "Innovation", "Competition"]

        Title: {title}
        First part of article: {content[:500]}
        """

        response = model.generate_content(prompt)
        topics_text = response.text.strip()

        # Try to parse as JSON
        try:
            topics = json.loads(topics_text)
            # Ensure it's a list of strings and limit to 3 topics
            if isinstance(topics, list) and all(isinstance(item, str) for item in topics):
                return topics[:3]
        except:
            # If JSON parsing fails, try to extract from text
            pass

        # Fallback to rule-based extraction
        return rule_based_topic_extraction(title, content)
    except Exception as e:
        print(f"Topic Extraction Error: {e}")
        # Fall back to rule-based extraction
        return rule_based_topic_extraction(title, content)


def rule_based_topic_extraction(title, content):
    """Extract multiple topics based on rules and keywords"""
    # Common topics in business/company news with keywords
    topic_keywords = {
        "Electric Vehicles": ["ev", "electric vehicle", "battery", "charging"],
        "Stock Market": ["stock", "shares", "market", "investor", "nasdaq", "wall street"],
        "Innovation": ["innovation", "tech", "technology", "breakthrough", "cutting-edge"],
        "Regulations": ["regulator", "compliance", "law", "legal", "government", "policy"],
        "Autonomous Vehicles": ["autonomous", "self-driving", "autopilot", "driver assist"],
        "Financial Results": ["earnings", "revenue", "profit", "quarterly", "financial"],
        "Product Launch": ["launch", "new", "introduce", "unveil", "announce"],
        "Leadership": ["ceo", "executive", "management", "appoint", "hire", "board"],
        "Partnerships": ["partner", "collaboration", "joint venture", "alliance", "deal"],
        "Competition": ["competitor", "rival", "versus", "market share", "industry"],
        "Sustainability": ["sustainable", "green", "environment", "carbon", "emission"],
        "Manufacturing": ["factory", "production", "manufacturing", "supply chain", "assembly"],
        "Global Markets": ["global", "international", "overseas", "export", "foreign"]
    }

    found_topics = []
    combined_text = (title + " " + content[:500]).lower()

    # Check for each topic's keywords in the text
    for topic, keywords in topic_keywords.items():
        if any(keyword in combined_text for keyword in keywords):
            found_topics.append(topic)

    # Limit to 3 topics, or return default if none found
    if found_topics:
        return found_topics[:3]
    else:
        return ["Company News"]


def analyze_sentiment(text):
    """Perform sentiment analysis on given text"""
    sentiment = analyzer.polarity_scores(text)
    if sentiment['compound'] >= 0.05:
        return "Positive"
    elif sentiment['compound'] <= -0.05:
        return "Negative"
    else:
        return "Neutral"


def generate_tts(text, filename=None):
    """Convert text to Hindi speech and save as an audio file

    Args:
        text: The text to convert to speech
        filename: Optional filename to use; if None, generates a temporary filename

    Returns:
        str: Path to the generated audio file
    """
    try:
        # Create a temporary directory if filename is not provided
        if filename is None:
            temp_dir = tempfile.gettempdir()
            filename = os.path.join(temp_dir, f"speech_{uuid.uuid4()}.mp3")

        # Make sure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)

        # Translate text to Hindi
        try:
            translated_text = translator.translate(text, dest="hi").text
        except Exception as e:
            print(f"Translation Error: {e}")
            # If translation fails, use original text
            translated_text = text

        # Convert Hindi text to speech
        tts = gTTS(text=translated_text, lang="hi", slow=False)
        tts.save(filename)

        print(f"Audio file generated at: {filename}")
        return filename
    except Exception as e:
        print(f"TTS Generation Error (detailed): {str(e)}")
        return None


def generate_comparative_tts(analysis, filename=None):
    """Generate Hindi TTS for the comparative analysis summary report"""
    try:
        # Create a temporary directory if filename is not provided
        if filename is None:
            temp_dir = tempfile.gettempdir()
            filename = os.path.join(temp_dir, f"comparative_speech_{uuid.uuid4()}.mp3")

        # Make sure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)

        # Get the final sentiment analysis text for TTS
        text = analysis.get("Final Sentiment Analysis", "No comparative analysis available")
        print(f"Generating speech for: {text}")

        # Generate the audio file
        return generate_tts(text, filename)
    except Exception as e:
        print(f"Comparative TTS Error: {str(e)}")
        return None