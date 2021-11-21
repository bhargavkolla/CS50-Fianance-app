import os

import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from flask_mail import Mail,Message
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)
app.config["MAIL_DEFAULT_SENDER"]=os.getenv("MAIL_DEFAULT_SENDER")
app.config["MAIL_PASSWORD"]=os.getenv("MAIL_PASSWORD")
app.config["MAIL_PORT"]=587
app.config["MAIL_SERVER"]="smtp.gmail.com"
app.config["MAIL_USE_TLS"]=True
app.config["MAIL_USERNAME"]=os.getenv("MAIL_USERNAME")
mail=Mail(app)


# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    name=db.execute("select username from users where id=?",session["user_id"])[0]["username"]
    stonk=db.execute("select stock,name,sum(shares) from customers group by stock,username having username=?",name)
    avail=0
    cash=float(db.execute("select cash from users where id=?",session["user_id"])[0]["cash"])
    if len(stonk)==0:
        stonk.append({"stock":"NONE","name":"NONE","sum(shares)":"-"})
        stonk[0]["price"]="0"
        stonk[0]["total"]="0"
    else:
        for row in stonk:
            x=float(lookup(row["stock"])["price"])
            row["price"]=x
            total=float(row["sum(shares)"])*x
            row["total"]=total
            avail=avail+total
    avail=avail+cash
    return render_template("index.html",stonk=stonk,cash=cash,avail=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method=="GET":
        return render_template("buy.html")
    if request.method=="POST":
        symbol=request.form.get("symbol")
        if not symbol:
            return apology("missing symbol")
        k=lookup(symbol)
        if k==None:
            return apology("Invalid stock symbol")
        stock_price=k["price"]
        namme=k["name"]
        symbol=k["symbol"]
        shares=request.form.get("shares")
        if not shares:
            return apology("missing shares")
        cash=float(shares)*float(stock_price)
        avail=db.execute("Select cash from users where id=?",session["user_id"])[0]["cash"]
        email=db.execute("Select email from users where id=?",session["user_id"])[0]["email"]
        if cash>avail:
            return apology("dude no enough money")
        now=datetime.datetime.now()
        name=db.execute("select username from users where id=?",session["user_id"])
        name=name[0]["username"]
        db.execute("INSERT INTO customers (username,type,stock,name,shares,price,cash,datetime) VALUES (?,?,?,?,?,?,?,?)",name,"BUY",symbol,namme,shares,stock_price,cash,now.strftime("%Y-%m-%d %H:%M:%S"))
        db.execute("UPDATE users SET cash=? where username=?",avail-cash,name)
        message=Message(f"buyed {namme} shares",recipients=[email])
        message.body=f"hey {name}, you buyed {shares} shares of {namme}({symbol}) each at a price of ${stock_price} for ${cash}"
        mail.send(message)
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    name=db.execute("select username from users where id=?",session["user_id"])[0]["username"]
    fil=db.execute("select type,stock,name,shares,price,cash,datetime from customers where username=?",name)
    return render_template("history.html",fil=fil)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method=="GET":
        return render_template("quote.html")
    if request.method=="POST":
        if not request.form.get("symbol"):
            return apology("missing symbol")
        quote=lookup(request.form.get("symbol"))
        if quote==None:
            return apology("invalid stock symbol")
        price=float(quote["price"])
        return render_template("quoted.html",quote=quote)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method=="GET":
       return render_template("register.html")
    if request.method=="POST":
        username=request.form.get("username")
        if not username:
            return apology("Enter username")
        row=db.execute("select * from users where username like ?",username)
        if len(row)!=0:
            return apology("username exists")
        email=request.form.get("email")
        if not email:
            return apology("Enter email")
        row=db.execute("select * from users where username like ?",email)
        if len(row)!=0:
            return apology("email exits")
        if not request.form.get("password"):
            return apology("password field empty")
        if not request.form.get("confirmation"):
            return apology("confirmation field empty")
        if request.form.get("password")!=request.form.get("confirmation"):
            return apology("passwords not matched")
        db.execute("INSERT INTO users (username,email,hash) VALUES (?,?,?)",username,email,generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8))
        message=Message("you are registered",recipients=[email])
        message.body=f"hey {username}, your mail is used for registering to CS50 finance app"
        mail.send(message)
        return redirect("/login")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method=="GET":
        name=db.execute("select username from users where id=?",session["user_id"])[0]["username"]
        fd=db.execute("select stock,name,sum(shares) from customers group by stock,username having username=?",name)
        return render_template("sell.html",fd=fd)
    if request.method=="POST":
        symbol=request.form.get("symbol")
        if not symbol:
            return apology("missing stock symbol")
        n=db.execute("select sum(shares) from customers group by stock having stock=?",symbol)[0]["sum(shares)"]
        if n==0:
            return apology("no shares of this stock")
        number=request.form.get("shares")
        if not number:
            return apology("missing number of stocks")
        number=int(number)
        if number>n:
            return apology("No enough stocks")
        else:
            name=db.execute("select username from users where id=?",session["user_id"])[0]["username"]
            now=datetime.datetime.now()
            k=lookup(symbol)
            stock_price=float(k["price"])
            cash=number*stock_price
            namme=k["name"]
            db.execute("INSERT INTO customers (username,type,stock,name,shares,price,cash,datetime) VALUES (?,?,?,?,?,?,?,?)",name,"SELL",symbol,namme,-number,stock_price,cash,now.strftime("%Y-%m-%d %H:%M:%S"))
            avail=db.execute("select cash from users where username=?",name)[0]["cash"]
            db.execute("UPDATE users SET cash=? where username=?",avail+cash,name)
            email=db.execute("select email from users where username=?",name)[0]["email"]
            message=Message(f"buyed {namme} shares",recipients=[email])
            message.body=f"hey {name}, you sold {number} shares of {namme}({symbol}) each at a price of ${stock_price} for ${cash}"
            mail.send(message)
            return redirect("/")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
