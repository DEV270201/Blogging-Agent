"""Public entry point for the blogging agent server"""

from Server.graph import blog_agent

if __name__ == "__main__":
    blog_agent.invoke({"topic": "Can you write a blog about the benefits of AI?"})
    # print(blog_agent.get_state())