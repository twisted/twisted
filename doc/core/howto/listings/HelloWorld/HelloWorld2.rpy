from twisted.web.woven import model, page

# The AttributeModel sets submodels as attributes of itself.
# May not be secure theoretically, but we're using it for simple purposes here.
model = model.AttributeModel()

model.setSubmodel("greeting", "Hello, world!")
model.setSubmodel("anInt", 5465465)
model.setSubmodel("aList", ['fred', 'bob', 'alice', 'joe'])
model.setSubmodel("aDict", {'some': 'stuff', 'goes': 'here'})

resource = page.Page(model, templateFile="HelloWorld2.html")
