from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user
from flask_mysqldb import MySQL
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import numpy as np
from io import BytesIO
import base64


app = Flask(__name__)
app.secret_key = '8520'

#MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'flask_users'

mysql = MySQL(app)


@app.route("/")
@app.route("/home")
def home():
    if 'username' in session:
        return render_template('home.html', username=session['username'])
    else:
        return render_template('home.html')
    
@app.route("/login", methods=['GET','POST'])
def login():
    if request.method == 'POST' :
        username = request.form['username']
        pwd = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute(f"SELECT username, password FROM tbl_users WHERE username = '{username}'")
        user = cur.fetchone()
        cur.close()
        if user and pwd == user[1]:
            session['username'] = user[0]
            return redirect(url_for('upload'))
        else:
            return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')


@app.route("/register",methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        pwd = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute(f"INSERT INTO tbl_users (username, password) VALUES ('{username}', '{pwd}')")
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('login'))
    return render_template('register.html')
    
@app.route('/logout')
def logout():
    session.pop('username',None)
    return redirect(url_for('home'))

@app.route("/recentgraphs")
def recentgraphs():
    return render_template("recentgraphs.html")

@app.route("/Contact")
def Contact():
    return render_template("Contact.html")

def preprocess_data(df):
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Extract hour, day, month, and day of week
    df['hour'] = df['timestamp'].dt.hour
    df['day'] = df['timestamp'].dt.day
    df['month'] = df['timestamp'].dt.month
    df['day_of_week'] = df['timestamp'].dt.dayofweek  # Monday=0, Sunday=6
    
    # Group by hour, day, month, and day of week
    df_hourly = df.groupby(['hour']).mean()
    df_daily = df.groupby(['day']).mean()
    df_monthly = df.groupby(['month']).mean()
    df_dayofweek = df.groupby(['day_of_week']).mean()
    
    # Create binary column for weekend (1 for weekend, 0 for weekday)
    df['weekend'] = np.where(df['day_of_week'].isin([5, 6]), 1, 0)  # Saturday=5, Sunday=6
    
    # Group by weekend
    df_weekly = df.groupby(['weekend']).mean()
    
    return df_hourly, df_daily, df_monthly, df_dayofweek, df_weekly

def create_plot(df, title):
    fig = px.line(df, x=df.index, y='kwh', title=title)
    return fig

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        # Read the CSV file
        file = request.files['file']
        df = pd.read_csv(file)
        
        # Preprocess the data
        df_hourly, df_daily, df_monthly, df_dayofweek, df_weekly = preprocess_data(df)
        
        # Identify anomalies based on hourly data
        std_dev_hourly = np.std(df['kwh'])
        anomalies_hourly = df_hourly[(df_hourly['kwh'] > df_hourly['kwh'].mean() + 2 * std_dev_hourly) | (df_hourly['kwh'] < df_hourly['kwh'].mean() - 2 * std_dev_hourly)]
        
        # Convert anomalies to null values
        for index in anomalies_hourly.index:
            df.loc[df['hour'] == index, 'kwh'] = np.nan
        
        # Fill null values using linear interpolation
        df['kwh'] = df['kwh'].interpolate(method='linear')
        
        # Recalculate aggregated data after interpolation
        df_hourly = df.groupby(['hour']).mean()
        df_daily = df.groupby(['day']).mean()
        df_monthly = df.groupby(['month']).mean()
        
        # Create interactive plots using Plotly for monthly, daily, and hourly data
        fig_monthly = create_plot(df_monthly, 'Monthly Energy Consumption')
        fig_daily = create_plot(df_daily, 'Daily Energy Consumption')
        fig_hourly = create_plot(df_hourly, 'Hourly Energy Consumption')

        # Convert plots to HTML format
        plot_html_monthly = fig_monthly.to_html(full_html=False, include_plotlyjs='cdn')
        plot_html_daily = fig_daily.to_html(full_html=False, include_plotlyjs='cdn')
        plot_html_hourly = fig_hourly.to_html(full_html=False, include_plotlyjs='cdn')

        return render_template('upload.html', plot_html_monthly=plot_html_monthly, plot_html_daily=plot_html_daily, plot_html_hourly=plot_html_hourly)
    
    return render_template('upload.html')

if __name__ == "__main__":
    app.run(debug=True)
