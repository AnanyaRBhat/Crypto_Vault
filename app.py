from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import random
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MongoDB client setup
client = MongoClient('mongodb://localhost:27017/')
db = client.the_bitcoin
users_collection = db.users
transactions_collection = db.transactions

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate.html')
def generate_page():
    return render_template('generate.html')

@app.route('/new_user.html')
def new_user_page():
    return render_template('new_user.html')

@app.route('/generate_bc.html')
def generate_bc_page():
    return render_template('generate_bc.html')

@app.route('/transaction.html')
def transaction_page():
    return render_template('transaction.html')

@app.route('/check_user', methods=['POST'])
def check_user():
    data = request.get_json()
    username = data['username']
    user = users_collection.find_one({"username": username})
    if user:
        return jsonify({"exists": True})
    else:
        return jsonify({"exists": False})

@app.route('/verify_password', methods=['POST'])
def verify_password():
    data = request.get_json()
    username = data['username']
    password = data['password']
    user = users_collection.find_one({"username": username})
    if user and check_password_hash(user['password'], password):
        return jsonify({"valid": True})
    else:
        return jsonify({"valid": False})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']
    user = users_collection.find_one({"username": username})
    if user and check_password_hash(user['password'], password):
        session['username'] = username
        return jsonify({"success": True, "username": username, "wallet_balance": user['wallet_balance']})
    else:
        return jsonify({"success": False})

@app.route('/logout', methods=['GET'])
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/register_user', methods=['POST'])
def register_user():
    data = request.get_json()
    username = data['username']
    password = generate_password_hash(data['password'])
    city = data['city']
    
    bitcoin_id = str(uuid.uuid4())
    
    new_user = {
        "username": username,
        "password": password,
        "bitcoin_id": bitcoin_id,
        "wallet_balance": 0.0,
        "city": city,
        "transactions": []
    }
    
    try:
        users_collection.insert_one(new_user)
        return jsonify({"success": True, "bitcoin_id": bitcoin_id})
    except:
        return jsonify({"success": False})

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    username = data['username']
    bitcoin_value = data['bitcoin_value']

    user = users_collection.find_one({"username": username})
    if not user:
        return jsonify({"error": "User not found"}), 404

    new_balance = user['wallet_balance'] + bitcoin_value
    users_collection.update_one({"username": username}, {"$set": {"wallet_balance": new_balance}})

    transaction_id = str(uuid.uuid4())
    transactions_collection.insert_one({
        "transaction_id": transaction_id,
        "username": username,
        "amount": bitcoin_value,
        "transaction_type": "generate",
        "timestamp": datetime.datetime.now()
    })

    return jsonify({"message": "Bitcoin generated", "new_balance": new_balance})

@app.route('/get_user_info', methods=['GET'])
def get_user_info():
    username = request.args.get('username')
    user = users_collection.find_one({"username": username}, {"_id": 0, "password": 0})
    if user:
        return jsonify(user)
    else:
        return jsonify({"error": "User not found"}), 404

@app.route('/transaction', methods=['POST'])
def transaction():
    data = request.get_json()
    sender_id = data['sender_id']
    receiver_id = data['receiver_id']
    amount = data['amount']

    sender = users_collection.find_one({"bitcoin_id": sender_id})
    receiver = users_collection.find_one({"bitcoin_id": receiver_id})

    if not sender or not receiver:
        return jsonify({"error": "Sender or receiver not found"}), 404

    if session.get('username') != sender['username']:
        return jsonify({"error": "You can only send from your own account"}), 403

    if sender['wallet_balance'] < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    new_sender_balance = sender['wallet_balance'] - amount
    new_receiver_balance = receiver['wallet_balance'] + amount

    users_collection.update_one({"bitcoin_id": sender_id}, {"$set": {"wallet_balance": new_sender_balance}})
    users_collection.update_one({"bitcoin_id": receiver_id}, {"$set": {"wallet_balance": new_receiver_balance}})

    transaction_id = str(uuid.uuid4())
    transactions_collection.insert_one({
        "transaction_id": transaction_id,
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "amount": amount,
        "timestamp": datetime.datetime.now()
    })

    return jsonify({"message": "Transaction successful", "new_balance": new_sender_balance})
@app.route('/transactions', methods=['GET'])
def get_transactions():
    transactions = list(transactions_collection.find({}, {"_id": 0}))
    for transaction in transactions:
        sender = users_collection.find_one({"bitcoin_id": transaction['sender_id']}, {"_id": 0, "city": 1})
        receiver = users_collection.find_one({"bitcoin_id": transaction['receiver_id']}, {"_id": 0, "city": 1})
        transaction['sender_city'] = sender['city'] if sender else 'Unknown'
        transaction['receiver_city'] = receiver['city'] if receiver else 'Unknown'
    return jsonify(transactions)

# Add this route to app.py or your Flask application file


@app.route('/viewboard.html', methods=['GET'])
def view_board():
    # Fetch all transactions from Transactions collection
    transactions = list(transactions_collection.find({}))

    # Dictionary to map bitcoin_id to city
    bitcoin_id_to_city = {}

    # Fetch cities from Users collection based on bitcoin_id
    for transaction in transactions:
        sender_bitcoin_id = transaction.get('sender_bitcoin_id')
        if sender_bitcoin_id not in bitcoin_id_to_city:
            user_data = users_collection.find_one({'bitcoin_id': sender_bitcoin_id})
            if user_data:
                bitcoin_id_to_city[sender_bitcoin_id] = user_data.get('city', 'Unknown')
            else:
                bitcoin_id_to_city[sender_bitcoin_id] = 'Unknown'

    # Enhance transactions with 'city' based on sender's bitcoin_id
    for transaction in transactions:
        sender_bitcoin_id = transaction.get('sender_bitcoin_id')
        transaction['city'] = bitcoin_id_to_city.get(sender_bitcoin_id, 'Unknown')

    return render_template('viewboard.html', transactions=transactions)

def viewboard_page():
    transactions = list(transactions_collection.find({}, {"_id": 0}))
    return render_template('viewboard.html', transactions=transactions)



if __name__ == '__main__':
    app.run(debug=True)
