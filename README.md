# AI-powered Iterative Search and Summarization

This repository contains a Streamlit application that demonstrates an AI-powered iterative search and summarization process. The application utilizes the Anthropic API for generating search queries, assessing relevance, and generating summaries based on the scraped content from relevant search results. It also integrates with the Tavily API for performing searches and retrieving image URLs.

## Demo

You can try out the live demo of the application here: [AI Iterative Search Demo](https://ai-iterative-search.streamlit.app/)

## Features

- AI-generated search queries based on user input topic
- Relevance assessment of search results using AI
- Web scraping of relevant search result pages
- AI-generated summaries of scraped content
- Iterative refinement of summaries based on follow-up queries
- Final comprehensive summary generation
- Saving search and summary history for future reference
- Integration with Tavily API for search functionality and image retrieval

## Requirements

To run the application locally, you need to have the following dependencies installed:

- Python 3.7 or higher
- Streamlit
- BeautifulSoup
- aiohttp
- anthropic
- tavily

You can install the required packages using pip:

```
pip install streamlit beautifulsoup4 aiohttp anthropic tavily-python
```

## Usage

1. Clone the repository:

```
git clone https://github.com/your-username/ai-iterative-search.git
```

2. Navigate to the project directory:

```
cd ai-iterative-search
```

3. Run the Streamlit application:

```
streamlit run sear.py
```

4. Open the application in your web browser using the provided URL.

5. Enter your Anthropic API key, Tavily API key, the topic you want to search for, and the desired number of iterations to refine the summary.

6. Click the "Generate Summary" button to start the iterative search and summarization process.

7. The application will display the progress, AI-generated search queries, relevant search results, images (if available), and the final comprehensive summary.

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgements

- [Anthropic](https://www.anthropic.com/) for providing the AI models and API.
- [Tavily](https://www.tavily.com/) for providing the search functionality and image retrieval API.
- [Streamlit](https://streamlit.io/) for the web application framework.
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) for web scraping.
- [aiohttp](https://docs.aiohttp.org/) for asynchronous HTTP requests.

Feel free to contribute to the project by submitting pull requests or reporting issues.
