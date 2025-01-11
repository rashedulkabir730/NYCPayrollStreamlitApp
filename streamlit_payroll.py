import pandas as pd
import boto3
from io import StringIO
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv
import os
import plotly.graph_objects as go

load_dotenv()

aws_access_key_id = os.getenv('ACCESS_KEY')
aws_secret_access_key = os.getenv('SECRET_KEY')

s3_client = boto3.client(
    service_name='s3',
    region_name='us-east-1',
    aws_access_key_id=aws_access_key_id, 
    aws_secret_access_key=aws_secret_access_key 
)

# Define the file and bucket
bucket_name = 'payrolldatanyckabir'
file_key = 'payroll.csv'


@st.cache_data
def load_data(file_key):
    # Get the file object from S3
    s3_object = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    # Read the content as CSV
    s3_data = s3_object['Body'].read().decode('utf-8')
    # Convert to a pandas DataFrame
    return pd.read_csv(StringIO(s3_data), low_memory=False)
payroll = load_data(file_key)



payroll[['base_salary', 'regular_hours', 'regular_gross_paid', 'ot_hours', 'total_ot_paid', 'total_other_pay']] = payroll[['base_salary', 'regular_hours', 'regular_gross_paid', 'ot_hours', 'total_ot_paid', 'total_other_pay']].astype(float)
payroll['agency_start_date'] = pd.to_datetime(payroll['agency_start_date'],errors='coerce')
payroll = payroll.dropna(subset=["agency_start_date"])
payroll['start_year'] = payroll['agency_start_date'].dt.year
payroll["pay_basis"] = payroll["pay_basis"].str.strip()
payroll['start_year'] = payroll['start_year'].astype(int)
payroll['fiscal_year'] = payroll['fiscal_year'].astype(int)
payroll['years_worked'] = payroll['fiscal_year'] - payroll['start_year']
def label_age(row):
    if row['years_worked'] < 5:
        return 'less than 5 years'
    elif 5 <= row['years_worked'] <= 10:
        return '6 - 10 years'
    elif 11 <= row['years_worked'] <= 20:
        return '11 - 20 years'
    elif 21 <= row['years_worked'] <= 30:
        return '21 - 30 years'
    elif 31 <= row['years_worked'] <= 40:
        return '31 - 40 years'
    else:
        return '40+ years'

payroll['years_worked_cat'] = payroll.apply(label_age, axis=1)
payroll['hourly_rate'] = payroll['base_salary'] / payroll['regular_hours']
payroll['base_salary'] = payroll['base_salary'].astype(float)
payroll = payroll[payroll['start_year'] <= 2024]
def per_hour(df):
    #change datatype to float
    df[['base_salary', 'regular_hours', 'regular_gross_paid', 'ot_hours', 'total_ot_paid', 'total_other_pay']] = df[['base_salary', 'regular_hours', 'regular_gross_paid', 'ot_hours', 'total_ot_paid', 'total_other_pay']].astype(float)

    df.loc[df['pay_basis'] == 'per Hour', 'base_salary'] = (
        df['base_salary'] * df['regular_hours']
    )
    #remove salary that is negative or zero
    df = df[df['base_salary'] > 1]
    return df

payroll = per_hour(payroll)




st.title('NYC Payroll Dashboard')



# Dropdowns and Slider
agency_list = payroll['agency_name'].unique().tolist()
selected_agency = st.sidebar.selectbox("Select Agency:", ["All"] + agency_list)

title_list = payroll['title_description'].unique().tolist()
selected_title = st.sidebar.selectbox("Select Title/Job:", ["All"] + title_list)

year_slider = st.sidebar.slider(
    "Select a range of years",
    min_value=payroll['start_year'].min(),
    max_value=payroll['start_year'].max(),
    value=(payroll['start_year'].min(), payroll['start_year'].max()),
    step=1,
)


salary_slider = st.sidebar.slider(
    "Select a range of salaries", 
    min_value=10000.0, 
    max_value=payroll['base_salary'].max(), 
    value=(10000.0, payroll['base_salary'].max()),  # Add the missing comma here
    step=1000.0
)



st.sidebar.markdown(
    """
    Made by [Rashedul Kabir](https://www.linkedin.com/in/rashedul-kabir/).
    """
)






def hiring_rates():
    payroll_filtered = payroll.copy()
    
    # Filter by Agency
    if selected_agency != "All":
        payroll_filtered = payroll_filtered[payroll_filtered['agency_name'] == selected_agency]

    # Filter by Title
    if selected_title != "All":
        payroll_filtered = payroll_filtered[payroll_filtered['title_description'] == selected_title]

    # Filter by Year Range
    payroll_filtered = payroll_filtered[
        (payroll_filtered['start_year'] >= year_slider[0]) & 
        (payroll_filtered['start_year'] <= year_slider[1])
    ]

    # Group and Calculate Percent Change
    hiring_rates = payroll_filtered.groupby('start_year').size().reset_index(name='num_hires')
    hiring_rates['pct_change'] = hiring_rates['num_hires'].pct_change() * 100

    # Sort and Limit Rows
    hiring_rates_sorted = hiring_rates.sort_values(by='start_year', ascending=False).head(25)

    title_parts = []
    if selected_agency != "All":
        title_parts.append(f"Agency: {selected_agency}")
    if selected_title != "All":
        title_parts.append(f"Title: {selected_title}")
    title_parts.append(f"Years: {year_slider[0]} - {year_slider[1]}")
    dynamic_title = "<br>".join(title_parts)

    # Create a combined bar and line chart using plotly.graph_objects
    fig = go.Figure()

    # Add bar chart for total hires
    fig.add_trace(go.Bar(
        x=hiring_rates_sorted['start_year'],
        y=hiring_rates_sorted['num_hires'],
        name="Total Hires",
        marker_color='lightblue',
        yaxis="y",
    ))

    # Add line chart for percentage change
    fig.add_trace(go.Scatter(
        x=hiring_rates_sorted['start_year'],
        y=hiring_rates_sorted['pct_change'],
        name="YoY % Change",
        mode='lines+markers',
        line=dict(color='orange', width=2),
        yaxis="y2",
    ))

    # Update layout for dual y-axes
    fig.update_layout(
        title=dict(
        text=f'Year-over-Year Total Hires & Percentage Change in Hires<br>{dynamic_title}',  # Add HTML line break
        x=0.5,  # Center the title
        xanchor="center",
        yanchor="top",
        ),

       # title=f'Year-over-Year Total Hires & Percentage Change in Hires ({dynamic_title})',
        xaxis=dict(title="Start Year"),
        yaxis=dict(
            title="Total Hires",
            titlefont=dict(color="lightblue"),
            tickfont=dict(color="lightblue"),
        ),
        yaxis2=dict(
            title="YoY % Change",
            titlefont=dict(color="orange"),
            tickfont=dict(color="orange"),
            overlaying="y",
            side="right",
        ),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.2),
        barmode='group',
        template="plotly_white",
        font=dict(family="Arial", size=14)

    )

    # Show the chart in Streamlit
    st.plotly_chart(fig)


def avg_base():
    payroll_filtered = payroll.copy()
    
    # Filter by Agency
    if selected_agency != "All":
        payroll_filtered = payroll_filtered[payroll_filtered['agency_name'] == selected_agency]

    # Filter by Title
    if selected_title != "All":
        payroll_filtered = payroll_filtered[payroll_filtered['title_description'] == selected_title]

    # Filter by Year Range
    payroll_filtered = payroll_filtered[
        (payroll_filtered['start_year'] >= year_slider[0]) & 
        (payroll_filtered['start_year'] <= year_slider[1])
    ]

    # Calculate average base salary
    avg_base_salary = payroll_filtered['base_salary'].mean()
    #avg_gross_salary = payroll_filtered['regular_gross_paid'].mean()

    # Get avg number of active workers from leave status col
    total_active_workers = payroll_filtered['leave_status_as_of_june_30'].str.contains('ACTIVE').sum()
    avg_years_worked = payroll_filtered['years_worked'].mean()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="Average Base Salary",
            value=f"${avg_base_salary:,.2f}" if avg_base_salary is not None else "N/A"
        )

    with col2:
        st.metric(
            label="Average Years Worked",
            value=f"{avg_years_worked:,.2f}" if avg_years_worked is not None else "N/A"
        )

    with col3:
        st.metric(
            label="Total Active Employees",
            value=f"{total_active_workers:,}" if total_active_workers is not None else "N/A"
        )

avg_base()
hiring_rates()
