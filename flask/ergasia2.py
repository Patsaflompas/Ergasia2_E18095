import collections
from warnings import resetwarnings
from pymongo import MongoClient
import pymongo
from pymongo.errors import DuplicateKeyError
from flask import Flask, request, jsonify, redirect, Response
from bson import json_util
from collections import defaultdict
import json
import uuid
import time
from datetime import date
import random

# Connect to our local MongoDB
client = MongoClient('mongodb://mongodb:27017/')

# Choose database
db = client['DSMarkets']

# Choose collections
users = db['Users']
products = db['Products']

# Initiate Flask App
app = Flask(__name__)

users_sessions = {}
admin_sessions = {}

def create_user_session(user_name):
    user_uuid = str(uuid.uuid1())
    users_sessions[user_uuid] = (user_name, time.time())
    return user_uuid  

def create_admin_session(admin_name):
    admin_uuid = str(uuid.uuid1())
    admin_sessions[admin_uuid] = (admin_name,time.time())
    return admin_uuid

def is_user_session_valid(user_uuid):
    return user_uuid in users_sessions

def is_admin_session_valid(admin_uuid):
    return admin_uuid in admin_sessions




#(user) Plain User Registration
@app.route('/createPlainUser', methods=['POST'])
def create_plain_user():
    # Request JSON data
    data = None 
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "name" in data or not "password" in data or not "email" in data:
        return Response("Information incomplete",status=500,mimetype="application/json")


    if users.find({"email":data["email"]}).count()==0: #check if a user with the same email already exists.
        newUser={"name":data['name'],"email":data['email'], "password":data['password'], "category":"plain_user", "orderHistory": None}
        users.insert_one(newUser)
        return Response(data['name']+" was added to the DSMarkets database!",status=200, mimetype='application/json') 
    
    else:
        return Response("A user with the email: "+ data['email'] +" already exists.",status=400, mimetype='application/json') 
#(user,admin) Users Login
@app.route('/usersLogin', methods=['POST'])
def users_login():
    # Request JSON data
    data = None 
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "email" in data or not "password" in data:
        return Response("Information incomplete",status=500,mimetype="application/json")

    loginUser = users.find_one({"email":data["email"],"password":data["password"]})
    
    global res

    if  loginUser != None:
        if loginUser["category"]=="plain_user":
            user_uuid = create_user_session(data["email"])
            res = {"user_uuid": user_uuid, "email": data['email']}
        if loginUser["category"]=="admin":
            admin_uuid = create_admin_session(data["email"])
            res = {"admin_uuid":admin_uuid,"email":data['email']}
        return Response(json.dumps(res),status=200, mimetype='application/json') 
       
    else:
        return Response("Wrong email or password",status=400,mimetype='application/json')
    
#(user) Product Search
@app.route('/productSearch', methods=['GET'])
def search_product():
   # Request JSON data
    data = None 
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "name" in data and not "category" in data and not "id" in data:
        return Response("Information incomplete",status= 500,mimetype="application/json")
    
    #User Authorization
    uuid = request.headers.get('authorization')
    if is_user_session_valid(uuid) == False:
        return Response("You are not authorized as a plain User!",status= 401,mimetype="application/json")


    if "name" in data:
        prod = list(products.find({"name": {"$regex":data["name"]}},{"stock":0}).sort('name'))
        if len(prod)==0:
            return Response("No product was found with the given name!",status = 404, mimetype='application/json')
        return Response(json.dumps(prod),status = 200, mimetype='application/json') 
    
    if "category" in data:
        prod = list(products.find({"category":data["category"]},{"stock":0}).sort('price'))
        if len(prod)==0:
            return Response("No product was found in that category!",status = 404, mimetype='application/json')
        return Response(json.dumps(prod),status=200, mimetype='application/json')
    
    if "id" in data:
        prod = list(products.find({"_id":data["id"]},{"stock":0}))
        if len(prod)==0:
            return Response("No product with the given Id was found!",status = 404, mimetype='application/json')
        return Response(json.dumps(prod),status=200, mimetype='application/json') 

shoppingCart = []
totalPrice = 0.00
cartSum = []

#(user) Add to shoping cart
@app.route('/addToCart', methods=['POST'])
def add_to_cart():
     # Request JSON data
    data = None 
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "id" in data or not "quantity" in data:
        return Response("Information incomplete",status= 500,mimetype="application/json")

    #User Authorization
    uuid = request.headers.get('authorization')
    if is_user_session_valid(uuid) == False:
        return Response("You are not authorized as a plain User!",status= 401,mimetype="application/json")


    prod = products.find_one({"_id":data["id"]})
    
    if prod == None:
        return Response("No product with the given Id was found!",status = 404, mimetype='application/json')
    if data['quantity'] > prod['stock']:
        return Response(json.dumps("You asked for: "+str(data['quantity'])+ " items, while there are only: "+str(prod['stock'])+" in stock"),status=404,mimetype='application/json')
    else:
        
        shoppingCartDummy = {'id':data['id'],'quantity':data['quantity'],'name':prod['name'],'sumPrice':(prod['price']*data['quantity'])}
        shoppingCart.append(shoppingCartDummy)
        
        global askedQuantity 
        askedQuantity = data['quantity']
        products.update_one({"_id":data['id']},{"$inc":{"stock":-askedQuantity}})
        
        global totalPrice
        totalPrice += shoppingCartDummy['sumPrice']
        
        global cartSum
        cartSum = [("Total Price of Cart: ",totalPrice)]

        return Response(json.dumps(shoppingCart+cartSum),status=200,mimetype='application/json')

#(user) Show Shopping Cart
@app.route('/showShoppingCart', methods=['GET'])
def show_shopping_cart():
    
    #User Authorization
    uuid = request.headers.get('authorization')
    if is_user_session_valid(uuid) == False:
        return Response("You are not authorized as a plain User!",status= 401,mimetype="application/json")


    if len(shoppingCart) == 0:
        return Response(json.dumps("Your Shopping Cart is Empty!"),status=404,mimetype='application/json')
    else:
        return Response(json.dumps(shoppingCart+cartSum),status=200,mimetype='application/json')

#(user) Delete items from Shopping Cart
@app.route('/deleteFromCart', methods=['DELETE'])
def delete_from_cart():
    # Request JSON data
    data = None 
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "id" in data:
        return Response("Information incomplete",status= 500,mimetype="application/json")
    
    #User Authorization
    uuid = request.headers.get('authorization')
    if is_user_session_valid(uuid) == False:
        return Response("You are not authorized as a plain User!",status= 401,mimetype="application/json")


    global cartSum
    global totalPrice
    global askedQuantity

    if len(shoppingCart)!=0:
        for i in range(len(shoppingCart)):
            if shoppingCart[i]["id"] == data["id"]:
                newTotalPrice = totalPrice - shoppingCart[i]["sumPrice"]
                totalPrice -= shoppingCart[i]["sumPrice"]
                cartSum = [("Total Price of Cart: ",totalPrice)]
                products.update_one({"_id":data['id']},{"$inc":{"stock":askedQuantity}})
                del shoppingCart[i]
                break
            else:
                return Response(json.dumps("Couldn't find the item with id : "+ str(data["id"])+" in your Shopping Cart"),status=404,mimetype='application/json')
    if len(shoppingCart)==0:
        return Response(json.dumps("Your Shopping Cart is Empty!"),status=404,mimetype='application/json')

    newCartSum = [("Total Price of Cart: ",newTotalPrice)]
    

    return Response(json.dumps(shoppingCart+newCartSum),status=200,mimetype='application/json')

#(user) Buy Product
@app.route('/buyProduct',methods=['POST'])
def buy_product():
    # Request JSON data
    data = None 
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "card number" in data:
        return Response("Information incomplete",status= 500,mimetype="application/json")

    #User Authorization
    uuid = request.headers.get('authorization')
    if is_user_session_valid(uuid) == False:
        return Response("You are not authorized as a plain User!",status= 401,mimetype="application/json")


    if len(shoppingCart)==0:
        return Response(json.dumps("Your Shopping Cart is Empty!"),status=404,mimetype='application/json')
    else:    
        cardNumber = str(data['card number'])
        if len(cardNumber) != 16:
            return Response(json.dumps("You have not given a 16 digit card number!"),status=400,mimetype='application/json')
        else: 
            receipt = ["Your receipt follows, with the shopping cart and the total price"] + shoppingCart + cartSum + ["Date and Hour: "+ str(date.today())+" "+ str(time.strftime("%H:%M:%S"))]
            users.update_one({"email":res["email"]},{"$set":{"orderHistory":receipt}})
            shoppingCart.clear()
            cartSum.clear()
            return Response(json.dumps(receipt),status=200,mimetype='application/json')

#(user) Show Order History
@app.route('/showOrderHistory',methods=['GET'])
def show_order_history():
    
    #User Authorization
    uuid = request.headers.get('authorization')
    if is_user_session_valid(uuid) == False:
        return Response("You are not authorized as a plain User!",status= 401,mimetype="application/json")


    global res
    orderHistory = users.find_one({"email":res["email"]},{"_id":0,"orderHistory":1})

    if orderHistory != None:
        return Response(json.dumps(orderHistory),status=200,mimetype='application/json')
    else:
        return Response(json.dumps("No order history found!"),status=404,mimetype='application/json')

#(user) Delete User
@app.route('/deleteUser',methods = ['DELETE'])
def delete_user():
    
    #User Authorization
    uuid = request.headers.get('authorization')
    if is_user_session_valid(uuid) == False:
        return Response("You are not authorized as a plain User!",status= 401,mimetype="application/json")


    deletedUser = users.find_one({"email":res['email']},{"_id":0})    
    stringDeleted = json.dumps(deletedUser) #metatrepw to dict se string mesw json.dumps giati den dexetai str kai dict mazi to msg 
    users.delete_one({'email':deletedUser['email']})
        
    return Response("The user " + stringDeleted + " was deleted!", status=200, mimetype='application/json')   

#(admin) Add new Product
@app.route('/addNewProduct',methods=['POST'])
def add_new_product():
    # Request JSON data
    data = None 
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "name" in data or not "category" in data or not "stock" in data or not "description" in data or not "price" in data:
        return Response("Information incomplete",status= 500,mimetype="application/json")

    #Admin Authorization
    uuid = request.headers.get('authorization')
    if is_admin_session_valid(uuid) == False:
        return Response("You are not authorized as an Admin!",status= 401,mimetype="application/json")


    prod = products.find_one({"name":data['name']})
    
    if prod == None:
        productId = random.randint(100000,999999)
        products.insert_one({"_id":productId,"name":data['name'],"category":data['category'],"stock":data['stock'],"description":data['description'],"price":data['price']})
        newProd = products.find_one({"_id":productId})
        return Response(json.dumps(newProd),status=200,mimetype='application/json')
    else:
        return Response("There is already a product with the name: " +data['name'],status=400,mimetype='application/json')

#(admin) Remove a Product
@app.route('/removeProduct',methods=['DELETE'])
def remove_product():
    # Request JSON data
    data = None 
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "id" in data :
        return Response("Information incomplete",status= 500,mimetype="application/json")

    #Admin Authorization
    uuid = request.headers.get('authorization')
    if is_admin_session_valid(uuid) == False:
        return Response("You are not authorized as an Admin!",status= 401,mimetype="application/json")


    prod = products.find_one({"_id":data['id']})

    if prod != None:
        deletedProduct = json.dumps(prod)
        products.delete_one({"_id":data["id"]})
        return Response(deletedProduct+" was deleted",status=200,mimetype='application/json')
    else:
        return Response("No product with the Id: " +str(data['id'])+" was found!",status=404,mimetype='application/json')

#(admin) Update a Product
@app.route('/updateProduct',methods=['PATCH'])
def update_product():
    # Request JSON data
    data = None 
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "id" in data:
        return Response("Information incomplete,Id missing",status= 500,mimetype="application/json")
    if not "name" in data and not "stock" in data and not "description" in data and not "price" in data:
        return Response("Information incomplete",status= 500,mimetype="application/json")

    #Admin Authorization
    uuid = request.headers.get('authorization')
    if is_admin_session_valid(uuid) == False:
        return Response("You are not authorized as an Admin!",status= 401,mimetype="application/json")


    prod = products.find_one({"_id":data['id']})

    if prod != None:
        
        if "name" in data:
            products.update_one({"_id":data['id']},{"$set":{"name":data['name']}})

        if "stock" in data:
            products.update_one({"_id":data['id']},{"$set":{"stock":data['stock']}})

        if "description" in data:
            products.update_one({"_id":data['id']},{"$set":{"description":data['description']}})

        if "price" in data:
            products.update_one({"_id":data['id']},{"$set":{"price":data['price']}})
        
        prod = products.find_one({"_id":data['id']})
        return Response(json.dumps(prod),status=200,mimetype='application/json')
    else:
        return Response("No product with Id: "+str(data['id'])+" was found!",status=404,mimetype='application/json')



#Run flask server debug at port 5000 
if __name__ == '__main__':
   app.run(debug=True, host='0.0.0.0', port=5000)