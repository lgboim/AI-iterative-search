import os
import json
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import anthropic
import re
import streamlit as st
from duckduckgo_search import AsyncDDGS

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
            'urls': urls
        }
        memory.append(new_entry)
        with open("memory.json", "w") as file:
            json.dump(memory, file)
    except Exception as e:
        print(f"Error during saving memory: {e}")

async def perform_search(query):
    try:
        search_results = await AsyncDDGS(proxy=None).text(query, max_results=10)
        return search_results
    except Exception as e:
        print(f"Exception occurred during search: {e}")
        return []

async def scrape_website_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    paragraphs = soup.find_all('p')
                    text = ' '.join([para.get_text(strip=True) for para in paragraphs])
                    return text[:4000]
                else:
                    return "Unable to fetch content due to non-200 status code."
        except Exception as e:
            print(f"Error during scraping: {e}")
            return f"Error during scraping: {e}"

def summarize_with_ai(content, query, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=3000,
        temperature=0.7,
        messages=[
            {"role": "user", "content": f"Please summarize the following content, super insightfull and structured. focusing on answering the question: '{query}'. Content: {content}"}
        ]
    )

    if response.content:
        if isinstance(response.content, list):
            return response.content[0].text
        else:
            return response.content
    else:
        return "No summary generated."

def generate_search_query(topic, attempt, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=100,
        temperature=0.7,
        messages=[
            {"role": "user", "content": f"Generate a search query for the following topic: '{topic}'. This is attempt {attempt}, so please provide a different query from the previous one. Think about search terms that will give you as much information as possible about it, not necessarily what the user wrote. Enclose the search query in double quotes."}
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

def generate_follow_up_query(summary, topic, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=100,
        temperature=0.7,
        messages=[
            {"role": "user", "content": f"Based on the following summary:\n{summary}\n\nGenerate a follow-up search query to further explore the topic '{topic}'. find things it didn't touch on or didn't give enough accurate information. Think about search terms that will give you as much information as possible about it, not necessarily what the user wrote. Enclose the search query in double quotes."}
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

def generate_final_summary(iteration_summaries, topic, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    combined_summaries = "\n".join(iteration_summaries)
    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=4000,
        temperature=0.7,
        messages=[
            {"role": "user", "content": f"Based on the following summaries from multiple iterations:\n{combined_summaries}\n\nGenerate a final comprehensive summary that captures the key points and insights related to the topic '{topic}'."}
        ]
    )

    if response.content:
        if isinstance(response.content, list):
            return response.content[0].text
        else:
            return response.content
    else:
        return "No final summary generated."

def assess_relevance(search_results, topic, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    relevant_results = []
    for result in search_results:
        title = result['title']
        snippet = result['body']
        url = result['href']

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1,
            temperature=0.7,
            messages=[
                {"role": "user", "content": f"Is the following search result relevant to the topic '{topic}'? Title: {title}, Snippet: {snippet}. Answer with 'yes' or 'no'."}
            ]
        )

        if isinstance(response.content, list):
            content = response.content[0].text.lower()
        else:
            content = response.content.lower()

        if content == 'yes':
            relevant_results.append(url)

    return relevant_results

async def main():
    st.title("AI-powered Search and Summarization")

    api_key = st.text_input("Enter your Anthropic API key:")
    topic = st.text_input("Enter a topic to search:")
    num_iterations = st.number_input("Enter the number of iterations to refine the summary:", min_value=1, value=1, step=1)

    if st.button("Generate Summary"):
        if not api_key:
            st.error("Please enter your Anthropic API key.")
            return

        search_query = topic
        iteration_summaries = []

        progress_bar = st.progress(0)
        progress_text = st.empty()
        final_summary_text = st.empty()

        for iteration in range(num_iterations):
            progress_bar.progress((iteration + 1) / num_iterations)
            progress_text.text(f"Iteration {iteration + 1}:")
            search_query = generate_search_query(search_query, iteration + 1, api_key)
            progress_text.text(f"AI-generated search query: {search_query}")

            search_results = await perform_search(search_query)
            relevant_results = assess_relevance(search_results, topic, api_key)

            if not relevant_results:
                progress_text.text("No relevant search results found. Trying again with a different query.")
                continue

            progress_text.text(f"Found {len(relevant_results)} relevant search results.")

            content_tasks = []
            urls = []
            for result in relevant_results:
                urls.append(result)
                content_tasks.append(scrape_website_content(result))

            scraped_contents = await asyncio.gather(*content_tasks)
            combined_content = "\n".join([content for content in scraped_contents if not content.startswith("Error")])

            iteration_summary = ""
            if combined_content:
                iteration_summary = summarize_with_ai(combined_content, topic, api_key)
                if iteration_summary:
                    iteration_summaries.append(iteration_summary)
                else:
                    progress_text.text("Failed to generate a summary for this iteration.")
            else:
                progress_text.text("Failed to scrape content from the relevant pages for this iteration.")

            if iteration < num_iterations - 1 and iteration_summary:
                follow_up_query = generate_follow_up_query(iteration_summary, topic, api_key)
                search_query = follow_up_query
                progress_text.text(f"AI-generated follow-up query for the next iteration: {follow_up_query}")

        progress_bar.empty()
        progress_text.empty()

        if iteration_summaries:
            final_summary = generate_final_summary(iteration_summaries, topic, api_key)
            final_summary_text.text(f"Final AI-generated summary:\n{final_summary}")
            save_memory(topic, final_summary, urls)
        else:
            final_summary_text.text("Failed to generate a final summary.")

if __name__ == "__main__":
    asyncio.run(main())
