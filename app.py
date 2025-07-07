from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import random
from models import db, User, Product, Establishment, ProductPrice

app = Flask(__name__)
app.config['SECRET_KEY'] = 'senha_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///market.db'
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_tables_and_seed():
    db.create_all()

    # --- Cria usuário admin padrão ---
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)

    # --- Seed richer de mercados, produtos e preços ---
    if not Product.query.first():
        est_names = ['Mercado A', 'Mercado B', 'Mercado C',
                     'Mercado D', 'Mercado E']
        prod_names = [
            'Arroz', 'Feijão', 'Leite', 'Óleo', 'Café',
            'Açúcar', 'Biscoito', 'Pão', 'Carne', 'Frango'
        ]

        # cria objetos
        ests = [Establishment(name=n) for n in est_names]
        prods = [Product(name=n) for n in prod_names]
        db.session.add_all(ests + prods)
        db.session.flush()  # gera IDs

        # gera preços randomizados entre R$3 e R$30
        for p in prods:
            for e in ests:
                price = round(random.uniform(3.0, 30.0), 2)
                db.session.add(ProductPrice(
                    product_id=p.id,
                    establishment_id=e.id,
                    price=price
                ))

    db.session.commit()

@app.route('/autocomplete', endpoint='autocomplete_api')
@login_required
def autocomplete():
    term = request.args.get('q', '')
    results = Product.query \
        .filter(Product.name.ilike(f'%{term}%')) \
        .order_by(Product.name) \
        .limit(10) \
        .all()
    suggestions = [p.name for p in results]
    return jsonify(suggestions)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Nome de usuário já existe')
        else:
            new_user = User(
                username=username,
                password=generate_password_hash(password),
                is_admin=False
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Cadastro realizado! Faça login.')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form['username']).first()
        if u and check_password_hash(u.password, request.form['password']):
            login_user(u)
            return redirect(url_for('dashboard'))
        flash('Credenciais inválidas')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if not current_user.is_admin:
        flash('Acesso negado: apenas administradores')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        pname = request.form['name'].strip()
        ename = request.form['establishment'].strip()
        price = float(request.form['price'])

        product = Product.query.filter_by(name=pname).first()
        if not product:
            product = Product(name=pname)
            db.session.add(product)

        est = Establishment.query.filter_by(name=ename).first()
        if not est:
            est = Establishment(name=ename)
            db.session.add(est)

        db.session.flush()
        db.session.add(ProductPrice(
            product_id=product.id,
            establishment_id=est.id,
            price=price
        ))
        db.session.commit()
        flash('Produto cadastrado com sucesso')
        return redirect(url_for('dashboard'))

    return render_template('add_product.html')

@app.route('/autocomplete')
@login_required
def autocomplete():
    term = request.args.get('q', '')
    results = Product.query \
        .filter(Product.name.ilike(f'%{term}%')) \
        .order_by(Product.name) \
        .limit(10) \
        .all()
    suggestions = [p.name for p in results]
    return jsonify(suggestions)

@app.route('/search_product', methods=['GET', 'POST'])
@login_required
def search_product():
    results = []
    if request.method == 'POST':
        pname = request.form['name'].strip()
        product = Product.query.filter_by(name=pname).first()
        if product:
            results = ProductPrice.query \
                .filter_by(product_id=product.id) \
                .order_by(ProductPrice.price) \
                .all()
        else:
            flash('Produto não encontrado')
    return render_template('search_product.html', results=results)

@app.route('/search_list', methods=['GET', 'POST'])
@login_required
def search_list():
    establishments = []
    all_products = Product.query.order_by(Product.name).all()
    if request.method == 'POST':
        csv_items = request.form.get('items', '')
        items = [i.strip() for i in csv_items.split(',') if i.strip()]
        prods = Product.query.filter(Product.name.in_(items)).all()
        ranking = []
        for est in Establishment.query.all():
            total, ok = 0, True
            for p in prods:
                pp = ProductPrice.query.filter_by(
                    product_id=p.id,
                    establishment_id=est.id
                ).first()
                if pp:
                    total += pp.price
                else:
                    ok = False
                    break
            if ok:
                ranking.append((est, total))
        establishments = sorted(ranking, key=lambda x: x[1])
    return render_template(
        'search_list.html',
        establishments=establishments,
        all_products=all_products
    )

if __name__ == '__main__':
    app.run(debug=True)
