text = """
<style>
        <--
body {
	margin:0px;
	padding:0px;
	font-family:verdana, arial, helvetica, sans-serif;
	color:#333;
	background-color:white;
	}
h1 {
/*        margin:0px 0px 15px 0px;*/
	padding:0px;
	font-size:28px;
	line-height:28px;
	font-weight:900;
	color:#ccc;
	}

h1.spaced {
    margin:0px 0px 15px 0px;
	padding:0px;
	font-size:28px;
	line-height:28px;
	font-weight:900;
	color:#ccc;
}

p {
	font:11px/20px verdana, arial, helvetica, sans-serif;
	margin:0px 0px 16px 0px;
	padding:0px;
	}
#Content>p {margin:0px;}
#Content>p+p {text-indent:30px;}

li {
    list-style-type:none;
}

td.spaced {
    margin:20px 0px 0px 0px;
}

table.content {
   	position:absolute;
	top:40px;
    left:15px;
/*        width:500px;*/
	padding:2px;
    background-color:#eff;
    border:1px dashed #222;
	line-height:17px;
}

/* margin settings = top right bottom left */
table.htdig {
    margin:41px 0px 10px 160px;
    width:500px;
	padding:2px;
    background-color:#eff;
    border:1px dashed #222;
	line-height:17px;
}

table.google {
    margin:10px 0px 20px 160px;
    width:500px;
	padding:2px;
    background-color:#eff;
    border:1px dashed #222;
	line-height:17px;
}


table.form {
    font-size:12px;
    font-style: bold;
}

table.menu {
	position:absolute;
	top:50px;
	left:20px;
/*        width:125px;*/
	padding:10px;
	background-color:#eee;
	border:1px dashed #999;
	line-height:17px;
}

a {
	color:#09c;
	font-size:11px;
	text-decoration:none;
	font-weight:600;
	font-family:verdana, arial, helvetica, sans-serif;
	}
a:link {color:#09c;}
a:visited {color:#07a;}
a:hover {background-color:#eee;}

.header {
	margin:50px 0px 10px 0px;
	padding:17px 0px 0px 20px;
	/* For IE5/Win's benefit height = [correct height] + [top padding] + [top and bottom border widths] */
	height:33px; /* 14px + 17px + 2px = 33px */
	border-style:solid;
	border-color:black;
	border-width:1px 0px; /* top and bottom borders: 1px; left and right borders: 0px */
	line-height:11px;
	background-color:#eee;

/* Here is the ugly brilliant hack that protects IE5/Win from its own stupidity. 
Thanks to Tantek Celik for the hack and to Eric Costello for publicizing it. 
IE5/Win incorrectly parses the "\"}"" value, prematurely closing the style 
declaration. The incorrect IE5/Win value is above, while the correct value is 
below. See http://glish.com/css/hacks.asp for details. */
	voice-family: "\"}\"";
	voice-family:inherit;
	height:14px; /* the correct height */
	}
/* I've heard this called the "be nice to Opera 5" rule. Basically, it feeds correct 
length values to user agents that exhibit the parsing error exploited above yet get 
the CSS box model right and understand the CSS2 parent-child selector. ALWAYS include
a "be nice to Opera 5" rule every time you use the Tantek Celik hack (above). */
body>.header {height:14px;}

.content {
	margin:0px 50px 50px 200px;
	padding:10px;
}

.menu {
	position:absolute;
	top:50px;
	left:20px;
	width:125px;
	padding:10px;
	background-color:#eee;
	border:1px dashed #999;
	line-height:17px;
/* Again, the ugly brilliant hack. */
	voice-family: "\"}\"";
	voice-family:inherit;
	width:150px;
	}
/* Again, "be nice to Opera 5". */
body > #Menu {width:150px;}
        -->
</style>
"""
