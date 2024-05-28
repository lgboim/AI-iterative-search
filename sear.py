import os
import json
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import anthropic
import re
import streamlit as st
import chardet
import ssl
import logging
from tavily import TavilyClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

st.set_option('client.showErrorDetails', True)

def load_memory():
    try:
        with open("memory.json", "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []
    except FileNotFoundError:
        return []

def save_memory(query, summary, urls):
    try:
        memory = load_memory()
        new_entry = {
            'query': query,
            'summary': summary,
            'urls': urls,
        }
        memory.append(new_entry)
        with open("memory.json", "w") as file:
            json.dump(memory, file)
    except Exception as e:
        print(f"Error during saving memory: {e}")

async def perform_search(query, api_key):
    client = TavilyClient(api_key=api_key)
    try:
        # Get the current event loop
        loop = asyncio.get_event_loop()

        # Execute the search asynchronously using run_in_executor
        search_results = await loop.run_in_executor(None, lambda: client.search(query, include_images=True))

        if search_results and 'results' in search_results:
            results = [{
                'title': result.get('title', ''),
                'body': result.get('content', ''),
                'href': result.get('url', '')
            } for result in search_results['results']]
            
            image_urls = search_results.get('images', [])
            
            return results, image_urls
        else:
            return [], []
    except Exception as e:
        logging.exception(f"Exception occurred during Tavily search: {e}")
        return [], []

async def scrape_website_content(session, url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    
    try:
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status == 200:
                html = await response.read()
                encoding = response.get_encoding()
                if encoding is None:
                    encoding = chardet.detect(html)['encoding']
                if encoding is None:
                    encoding = 'utf-8'  # Fallback to a default encoding
                html = html.decode(encoding, errors='ignore')
                soup = BeautifulSoup(html, 'html.parser')
                paragraphs = soup.find_all('p')
                text = ' '.join([para.get_text(strip=True) for para in paragraphs])
                logging.info(f"Scraped content from URL '{url}': {text[:100]}...")
                return text[:4000]
            else:
                logging.warning(f"Unable to fetch content from URL '{url}' due to non-200 status code.")
                return "Unable to fetch content due to non-200 status code."
    except aiohttp.ClientError as e:
        logging.exception(f"Error during scraping: {e}")
        return f"Error during scraping: {e}"
    except asyncio.TimeoutError:
        logging.warning(f"Timeout occurred while scraping URL: {url}")
        return f"Timeout occurred while scraping URL: {url}"
    except UnicodeDecodeError as e:
        logging.exception(f"Error during decoding: {e}")
        return f"Error during decoding: {e}"
    except Exception as e:
        logging.exception(f"Error during scraping: {e}")
        return f"Error during scraping: {e}"


def summarize_with_ai(content, query, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=3000,
        temperature=0.7,
        messages=[
            {"role": "user", "content": f"Please summarize the following content, super detailed, insightful and structured. focusing on answering the question: '{query}'. Content: {content}"}
        ]
    )

    if response.content:
        if isinstance(response.content, list):
            summary = response.content[0].text
            return summary
        else:
            summary = response.content
            return summary
    else:
        return "No summary generated."

def generate_follow_up_query(summary, topic, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=100,
        temperature=0.7,
        messages=[
            {"role": "user", "content": f"Based on the following summary:\n{summary}\n\nGenerate a follow-up search query to further explore the topic '{topic}'. Find things it didn't touch on or didn't give enough accurate information. Think about search terms that will give you as much information as possible about it, not necessarily what the user wrote. Try to get to the root of things. Enclose the search query in double quotes."}
        ]
    )

    if response.content:
        content = str(response.content)
        search_query = re.findall(r'"(.*?)"', content)
        if search_query:
            return search_query[0]
        else:
            return topic
    else:
        return topic

def generate_search_query(topic, attempt, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=100,
        temperature=0.7,
        messages=[
            {"role": "user", "content": f"Generate a search query for the following topic: '{topic}'. This is attempt {attempt}, so please provide a different query from the previous one. Think about search terms that will give you as much information as possible about it, not necessarily what the user wrote. Try to get to the root of things. Enclose the search query in double quotes."}
        ]
    )

    if response.content:
        content = str(response.content[0].text)
        search_query = re.findall(r'"(.*?)"', content)
        if search_query:
            return search_query[0]
        else:
            return topic
    else:
        return topic
        
def generate_final_summary(iteration_summaries, topic, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    combined_summaries = "\n".join(iteration_summaries)
    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=4000,
        temperature=0.7,
        messages=[
            {"role": "user", "content": f"Based on the following summaries from multiple iterations:\n{combined_summaries}\n\nGenerate a final comprehensive structured detailed summary that captures all the points and insights related to the topic '{topic}'."}
        ]
    )

    if response.content:
        if isinstance(response.content, list):
            final_summary = response.content[0].text
            return final_summary
        else:
            final_summary = response.content
            return final_summary
    else:
        return "No final summary generated."

def assess_relevance(search_results, topic, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    relevant_results = []

    search_result_texts = [f"Title: {result['title']}, Snippet: {result['body']}" for result in search_results]
    search_result_urls = [result['href'] for result in search_results]

    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=500,
        temperature=0.7,
        messages=[
            {"role": "user", "content": f"For each of the following search results, determine if it is relevant to the topic '{topic}'. Answer with a list of numbers corresponding to the relevant search results.\n\n" + "\n".join(search_result_texts)}
        ]
    )

    if isinstance(response.content, list):
        content = response.content[0].text.strip()
    else:
        content = response.content.strip()

    relevant_indices = [int(index.strip()) for index in content.split(",") if index.strip().isdigit()]

    if relevant_indices:
        relevant_results = [search_result_urls[index] for index in relevant_indices if 0 <= index < len(search_result_urls)]
    else:
        relevant_results = search_result_urls

    return relevant_results

async def process_iteration(iteration, topic, api_key, tavily_api_key, session, progress_text, num_iterations, iteration_summaries):
    if iteration == 0:
        search_query = generate_search_query(topic, 1, api_key)
    else:
        if iteration_summaries:
            progress_text.text(f"🔍 Generating follow-up query for iteration {iteration + 1}...")
            search_query = generate_follow_up_query(iteration_summaries[-1], topic, api_key)
            progress_text.text(f"🤖 AI-generated follow-up query for iteration {iteration + 1}: {search_query}")
        else:
            progress_text.text(f"❌ No summary available from previous iteration. Using the original topic as the search query.")
            search_query = generate_search_query(topic, iteration + 1, api_key)

    progress_text.text(f"🌐 Performing search: {search_query}")
    search_results, image_urls = await perform_search(search_query, tavily_api_key)

    progress_text.text(f"🧐 Assessing relevance of search results...")
    relevant_results = assess_relevance(search_results, topic, api_key)

    if not relevant_results:
        progress_text.text("😕 No relevant search results found. Trying again with a different query.")
        return None, []

    progress_text.text(f"✅ Found {len(relevant_results)} relevant search results.")

    progress_text.text(f"📄 Scraping content from relevant pages...")
    content_tasks = []
    for url in relevant_results:
        content_tasks.append(scrape_website_content(session, url))

    scraped_contents = await asyncio.gather(*content_tasks)

    combined_content = "\n".join([content for content in scraped_contents if not content.startswith("Error")])

    iteration_summary = ""
    if combined_content:
        progress_text.text(f"📝 Generating summary for iteration {iteration + 1}...")
        iteration_summary = summarize_with_ai(combined_content, topic, api_key)

        if not iteration_summary:
            progress_text.text("❌ Failed to generate a summary for this iteration.")
    else:
        progress_text.text("❌ Failed to scrape content from the relevant pages for this iteration.")

    return iteration_summary, image_urls

async def main():
    st.set_page_config(page_title="AI-powered Search and Summarization", layout="wide")
    
    with st.sidebar:
        st.title("Search Settings")
        anthropic_api_key = st.text_input("Enter your Anthropic API key:", type="password")
        tavily_api_key = st.text_input("Enter your Tavily API key:", type="password")
        topic = st.text_input("Enter a topic to search:")
        num_iterations = st.number_input("Enter the number of iterations to refine the summary:", min_value=1, value=1, step=1)
        generate_button = st.button("Generate Summary")

    if generate_button:
        if not anthropic_api_key:
            st.error("Please enter your Anthropic API key.")
            return
        if not tavily_api_key:
            st.error("Please enter your Tavily API key.")
            return

        progress_bar = st.progress(0)
        progress_text = st.empty()

        iteration_summaries = []
        image_urls_list = []

        ssl_context = ssl.create_default_context()
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            for iteration in range(num_iterations):
                iteration_summary, image_urls = await process_iteration(iteration, topic, anthropic_api_key, tavily_api_key, session, progress_text, num_iterations, iteration_summaries)
                if iteration_summary:
                    iteration_summaries.append(iteration_summary)
                    image_urls_list.extend(image_urls)
                    
                progress_bar.progress((iteration + 1) / num_iterations)

            progress_bar.empty()
            progress_text.empty()

            col1, col2 = st.columns(2)

            with col1:
                if image_urls_list:
                    st.image(image_urls_list, use_column_width=True)
                else:
                    st.write("No images found.")

            with col2:
                if iteration_summaries:
                    progress_text.text(f"📜 Generating final summary...")
                    final_summary = generate_final_summary(iteration_summaries, topic, anthropic_api_key)

                    st.write(f"🎉 Final AI-generated summary:\n{final_summary}")
                    save_memory(topic, final_summary, [])
                else:
                    st.write("❌ Failed to generate a final summary.")
if __name__ == "__main__":
    asyncio.run(main())
