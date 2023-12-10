from bson import ObjectId
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
import secrets
from datetime import datetime

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.secret_key = 'your_secret_key'
bcrypt = Bcrypt(app)

# MongoDB configuration
client = MongoClient('mongodb://localhost:27017/')
db = client['adb']
users_collection = db['customers']
admin_users_collection = db['admin']
bank_officers_collection = db['bankofficer']
transactions_collection = db['transactions']
accounts_collection = db['accounts']
banks_collection = db['banks']


class User:
    def __init__(self, username, password):
        self.username = username
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')


@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fname = request.form.get('fname')
        lname = request.form.get('lname')
        dob = request.form.get('dob')
        address = request.form.get('address')
        contact = request.form.get('contact')
        ssn = request.form.get('ssn')
        username = request.form.get('username')
        password = request.form.get('password')
        cpassword = request.form.get('cpassword')
        bank_id = request.form.get('bank_id')

        # Check if passwords match
        if password != cpassword:
            flash('Password and Confirm Password do not match', 'error')
            return redirect(url_for('register'))

        # Hash the password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        user = {
            "fname": fname,
            "lname": lname,
            "dob": dob,
            "address": address,
            "contact": contact,
            "ssn": ssn,
            "username": username,
            "password": hashed_password,
            "isActive": False  # You can set this to True if you want to activate the account immediately
        }

        user_inserted = users_collection.insert_one(user)

        # Generate a random account number and debit card number
        account_number = secrets.token_hex(5)  # Adjust length as needed
        debit_card_number = secrets.token_hex(8)  # Adjust length as needed

        # Create an account for the user
        account = {
            "accountNumber": account_number,
            "CustomerId": user_inserted.inserted_id,  # MongoDB generated ID
            "balance": 0,
            "debitCard": debit_card_number,
            "bankId": ObjectId(bank_id)
        }

        # Assuming 'accounts' is your account collection
        db['accounts'].insert_one(account)

        flash('Registration successful', 'success')
        return redirect(url_for('login'))

    banks = list(db['banks'].find({}))
    return render_template('register.html',banks=banks)



@app.route('/approve_users')
def approve_users():
    if 'username' in session and session['user_type'] == 'admin':
        username = session['username']
        unapproved_users = users_collection.find({"isActive": False})
        return render_template('approve_users.html', users=unapproved_users, username=username)
    else:
        return redirect(url_for('login'))

@app.route('/approve_user/<user_id>', methods=['GET', 'POST'])
def approve_user(user_id):
    if 'username' in session and session['user_type'] == 'admin':
        username = session['username']
        user = users_collection.find_one({'_id': ObjectId(user_id)})

        if request.method == 'POST':
            category_id = request.form.get('account_type')
            users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'isActive': True, 'accountTypeId': ObjectId(category_id)}})
            return redirect(url_for('approve_users'))

        # Fetch account types from the category collection along with their IDs
        categories = db['category'].find()
        account_types = [{'id': str(category['_id']), 'type': category['AccountType']} for category in categories]
        account=accounts_collection.find_one({'CustomerId': ObjectId(user_id)})
        bank = banks_collection.find_one({'_id': ObjectId(account['bankId'])})
        return render_template('approve_user.html', user=user, account_types=account_types, username=username, bank=bank)
    else:
        return redirect(url_for('login'))

@app.route('/deposit_money', methods=['GET', 'POST'])
def deposit_money():
    if 'username' in session and session['user_type'] == 'admin':
        username=session['username']
        if request.method == 'POST':
            account_number = request.form.get('account_number')
            deposit_amount = float(request.form.get('deposit_amount'))

            # Fetch the account and update the balance
            account = db['accounts'].find_one({'accountNumber': account_number})
            if account:
                new_balance = account['balance'] + deposit_amount
                db['accounts'].update_one({'accountNumber': account_number}, {'$set': {'balance': new_balance}})
                # Record the deposit transaction
                transaction_credit = {
                    "accountId": account_number,
                    "senderAccount": "Bank Officer - " + session['username'],  # Identifies the bank officer
                    "amount": round(deposit_amount, 2),
                    "type": "Deposit",
                    "dateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                db['transactions'].insert_one(transaction_credit)

                flash('Deposit successful', 'success')
            else:
                flash('Account not found', 'error')

            return redirect(url_for('deposit_money'))

        return render_template('deposit_money.html',username=username)
    else:
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if the user is an admin
        admin_user = admin_users_collection.find_one({'username': username})
        if admin_user and bcrypt.check_password_hash(admin_user['password'], password):
            session['username'] = username
            session['user_type'] = 'admin'  # Set user type to 'admin'
            return redirect(url_for('admin_dashboard'))

        # Check if the user is an admin
        bank_officer = bank_officers_collection.find_one({'username': username})
        if bank_officer and bcrypt.check_password_hash(bank_officer['password'], password):
            session['username'] = username
            session['user_type'] = 'admin'  # Set user type to 'admin'
            return redirect(url_for('bankofficer_dashboard'))

        user = users_collection.find_one({'username': username})
        if user and bcrypt.check_password_hash(user['password'], password):
            if user.get('isActive', False):  # Check if user is approved
                session['username'] = username
                return redirect(url_for('dashboard'))
            else:
                flash('Account not yet approved by admin', 'error')
                return redirect(url_for('login'))

        flash('Invalid username or password', 'error')  # Flash message for invalid login

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        username = session['username']
        user = users_collection.find_one({'username': username})

        if user:
            customer_id = user['_id']

            # Fetch all accounts associated with the user
            accounts = list(accounts_collection.find({'CustomerId': customer_id}))

            # Attach bank details to each account
            for account in accounts:
                bank = banks_collection.find_one({'_id': account['bankId']})
                account['bankName'] = bank['name'] if bank else 'Unknown Bank'

                # Fetch and format transactions for each account
                transactions = list(transactions_collection.find({
                    '$or': [
                        {'accountId': account["accountNumber"]},  # Credit transactions
                        {'receiverAccount': account["accountNumber"]}  # Debit transactions
                    ]
                }).sort('dateTime', -1))
                last_transaction = transactions[0] if transactions else None

                for transaction in transactions:
                    if isinstance(transaction['dateTime'], str):
                        transaction_datetime = datetime.strptime(transaction['dateTime'], "%Y-%m-%d %H:%M:%S")
                    else:
                        transaction_datetime = transaction['dateTime']

                    print(transaction)
                    # Format dateTime to 12-hour format
                    transaction['dateTime'] = transaction_datetime.strftime('%I:%M %p %d-%m-%Y')



                account['transactions'] = transactions
                account['lastTransaction'] = transactions[0] if transactions else None
                account_type = "Not Available"  # Default if not found
                if 'accountTypeId' in user:
                    category = db['category'].find_one({'_id': user['accountTypeId']})
                    account_type = category['AccountType'] if category else account_type

                if account:
                    account_details = {
                        'fname': user['fname'],
                        'lname': user['lname'],
                        'balance': account['balance'],
                        'debitCardNumber': account['debitCard'],
                        'accountNumber': account['accountNumber'],
                        'address': user['address'],
                        'ssn': user['ssn'],
                        'accountType': account_type
                    }

            return render_template('dashboard.html', username=username, accounts=accounts, account_details=account_details, transactions=transactions, last_transaction=last_transaction)

        else:
            return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))



@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'username' in session:
        username = session['username']
        # Fetch user details
        user = users_collection.find_one({'username': username})

        if request.method == 'POST':
            # Extract transfer details from form
            sender_account_number = request.form.get('sender_account')
            account_number = sender_account_number
            receiver_account_number = request.form.get('receiver_account')
            amount = float(request.form.get('amount'))

            # Verify that the sender has enough balance
            sender_account = db['accounts'].find_one({'accountNumber': sender_account_number})
            if sender_account and sender_account['balance'] >= amount:
                # Proceed with the transfer
                db['accounts'].update_one(
                    {'accountNumber': sender_account_number},
                    {'$inc': {'balance': -amount}}
                )
                db['accounts'].update_one(
                    {'accountNumber': receiver_account_number},
                    {'$inc': {'balance': amount}}
                )

                # Record the transactions
                transaction_debit = {
                    "accountId": sender_account_number,
                    "receiverAccount": receiver_account_number,
                    "amount": -round(amount, 2), # Negative amount for debit
                    "type": "Transfer Debit",
                    "dateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Current date and time
                }
                transaction_credit = {
                    "accountId": receiver_account_number,
                    "senderAccount": sender_account_number,
                    "amount": round(amount, 2),
                    "type": "Transfer Credit",
                    "dateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Current date and time
                }

                db['transactions'].insert_one(transaction_debit)
                db['transactions'].insert_one(transaction_credit)

                flash('Transfer completed successfully', 'success')
            else:
                flash('Insufficient funds', 'error')

            return redirect(url_for('transfer'))

        if user:
            # Assuming the customer ID is stored in the user's document
            customer_id = user['_id']
            # Fetch account details
            account = db['accounts'].find_one({'CustomerId': customer_id})

            if account:
                user_account_number = account['accountNumber']
                balance = round(account['balance'], 2)
                return render_template('transfer.html', username=username, user_account_number=user_account_number, balance=balance)
            else:
                return 'No account found for the user'
        else:
            return redirect(url_for('login'))

    # Render transfer form on GET request
    return render_template('transfer.html', username=session['username'])


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' in session and session['user_type'] == 'admin':
        total_users = users_collection.count_documents({})
        bank_officers = bank_officers_collection.count_documents({})
        total_transactions = transactions_collection.count_documents({})

        return render_template('admin_dashboard.html',
                               username=session['username'],
                               total_users=total_users,
                               bank_officers=bank_officers,
                               total_transactions=total_transactions)
    else:
        return redirect(url_for('login'))

@app.route('/bankofficer_dashboard')
def bankofficer_dashboard():
    if 'username' in session and session['user_type'] == 'admin':
        total_users = users_collection.count_documents({})
        bank_officers = bank_officers_collection.count_documents({})
        total_transactions = transactions_collection.count_documents({})

        return render_template('bankofficer_dashboard.html',
                               username=session['username'],
                               total_users=total_users,
                               bank_officers=bank_officers,
                               total_transactions=total_transactions)
    else:
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/ecommerce')
def ecommerce():
    return render_template('ecommerce/index.html')


@app.route('/payment')
def payment():
    price = request.args.get('price', '0.00')  # Default to 0.00 if not provided
    return render_template('ecommerce/payment.html', price=price)


@app.route('/process_payment', methods=['POST'])
def process_payment():
    debit_card_number = request.form.get('debitCardNumber')
    amount = float(request.form.get('amount'))

    # Fetch the account by debit card number
    account = db['accounts'].find_one({'debitCard': debit_card_number})

    if account and account['balance'] >= amount:
        # Deduct the amount from the account balance
        new_balance = account['balance'] - amount
        db['accounts'].update_one({'debitCard': debit_card_number}, {'$set': {'balance': new_balance}})

        # Record the transaction
        transaction = {
            "accountId": account['accountNumber'],
            "receiverAccount": "Online Ecommerce",
            "amount": -amount,
            "type": "Debit Card Purchase",
            "dateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        db['transactions'].insert_one(transaction)

        return 'Payment successful'
    else:
        return 'Payment failed: Insufficient funds or invalid card number'


@app.route('/get_account_name', methods=['POST'])
def get_account_name():
    account_number = request.form.get('account_number')
    account = db['accounts'].find_one({'accountNumber': account_number})
    if account:
        customer_id = account['CustomerId']
        customer = db['customers'].find_one({'_id': customer_id})
        if customer['fname']:
            return {'name': customer['fname']}
        elif customer['name']:
            return {'name':customer['name']}
    return {'name': ''}


@app.route('/manage_users')
def manage_users():
    if 'username' in session and session['user_type'] == 'admin':
        username = session['username']
        # Fetch user data from the database
        users = users_collection.find({})
        return render_template('manage_users.html', users=users, username=username)
    else:
        return redirect(url_for('login'))


@app.route('/edit_user/<user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'username' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))

    user = users_collection.find_one({'_id': ObjectId(user_id)})
    if not user:
        return 'User not found'

    if request.method == 'POST':
        # Extract data from the form
        updated_fname = request.form.get('fname')
        updated_lname = request.form.get('lname')
        updated_dob = request.form.get('dob')
        updated_address = request.form.get('address')
        updated_contact = request.form.get('contact')
        updated_ssn = request.form.get('ssn')
        updated_username = request.form.get('username')

        # Update user information in the database
        users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'fname': updated_fname,
                'lname': updated_lname,
                'dob': updated_dob,
                'address': updated_address,
                'contact': updated_contact,
                'ssn': updated_ssn,
                'username': updated_username,
                # Add more fields as needed
            }}
        )

        return redirect(url_for('manage_users'))

    return render_template('edit_user.html', user=user)



@app.route('/delete_user/<user_id>', methods=['GET'])
def delete_user(user_id):
    if 'username' in session and session['user_type'] == 'admin':
        users_collection.delete_one({'_id': ObjectId(user_id)})
        return redirect(url_for('manage_users'))
    else:
        return redirect(url_for('login'))


@app.route('/view_transactions')
def view_transactions():
    if 'username' in session and session['user_type'] == 'admin':
        username = session['username']
        transactions = db['transactions'].find({}).sort('dateTime', -1)

        # Enhance transactions with user name and separate credit/debit
        enhanced_transactions = []
        for transaction in transactions:
            account = db['accounts'].find_one({'accountNumber': transaction['accountId']})
            if account:
                user_id = account['CustomerId']
                user = db['customers'].find_one({'_id': user_id})
                first_name = user.get('fname', 'Unknown')
                last_name = user.get('lname', '')
                user_name = f"{first_name} {last_name}".strip()
            else:
                user_name = 'Unknown'

            # Convert dateTime to a datetime object if it's not already
            if isinstance(transaction['dateTime'], str):
                transaction_datetime = datetime.strptime(transaction['dateTime'], "%Y-%m-%d %H:%M:%S")
            else:
                transaction_datetime = transaction['dateTime']

            # Format dateTime to 12-hour format
            formatted_date = transaction_datetime.strftime('%I:%M %p %d-%m-%Y')

            transaction_data = {
                '_id': transaction['_id'],
                'accountId': transaction['accountId'],
                'accountName': user_name,  # Add user name
                'type': transaction['type'],
                'amount': transaction['amount'],
                'formattedDate': formatted_date  # Use formatted date
            }
            enhanced_transactions.append(transaction_data)

        return render_template('view_transactions.html', transactions=enhanced_transactions, username=username)
    else:
        return redirect(url_for('login'))



@app.route('/add-user', methods=['GET'])
def add_user():
    if 'username' in session and session['user_type'] == 'admin':
        username = session['username']
        return render_template('add_user.html', username=username)
    else:
        return redirect(url_for('login'))


@app.route('/create-user', methods=['POST'])
def create_user():
    if 'username' in session and session['user_type'] == 'admin':
        username = request.form['username']
        name = request.form.get('name')  # Add a name field in your form for bank officers
        password = request.form['password']
        role = request.form['role']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        if role == 'bankofficer':
            bank_officers_collection.insert_one({
                "name": name,
                "username": username,
                "password": hashed_password,
                "deposit": True  # Assuming all bank officers have deposit rights
            })
        elif role == 'admin':
            admin_users_collection.insert_one({
                "username": username,
                "password": hashed_password
            })

        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
