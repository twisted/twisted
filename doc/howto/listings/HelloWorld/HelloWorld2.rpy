from twisted.web.woven import model, page

model = model.Model()

model.setSubmodel("greeting", "Hello, world!")
model.setSubmodel("anInt", 5465465)
model.setSubmodel("aList", ['fred', 'bob', 'alice', 'joe'])
model.setSubmodel("aDict", {'some': 'stuff', 'goes': 'here'})

resource = page.Page(model, templateFile="HelloWorld2.html")
