from twisted.web.woven import page

resource = page.Page("Hello, world!", templateFile = "HelloWorld.html")
