# Nimbus Financial Data Explorer

## 1. Basic overview

Nimbus is a cloud-enabled financial intelligence dashboard built to help analysts and investors quickly explore company information by ticker symbol. The project pulls market and company data from Yahoo Finance and presents it in a simple web interface using Streamlit.

The application is intended to support desk research by surfacing a mix of financial metrics, recent news, and analyst information in a single place. It provides a lightweight front-end for exploring public market data without requiring a large data platform or complex architecture.

In this project, the app is designed to be usable both as a local demonstration and as a cloud deployment on AWS. The overall objective is to showcase how a simple Python application can be packaged, deployed, and run in a cloud environment while remaining easy to use for students and analysts.

## 2. Structure of the project

- `src/app.py`: Streamlit app entry point.
- `src/analysis.py`: Shared Yahoo Finance data functions.
- `assets/nimbus-logo-icon.png`: Square logo used for the browser tab icon.
- `assets/nimbus-logo-wide.png`: Wide logo used in the main dashboard heading.
- `src/features/`: Future one-file-per-feature modules; see its README.
- `filings.ipynb`, `news.ipynb`, `stock_price_ratings.ipynb`: Exploratory notebooks.

- src/app.py: Streamlit application entry point and dashboard user interface.
- src/analysis.py: Core functions that request and prepare financial data from Yahoo Finance.
- src/features/: Place for future feature-based modules as the project expands.
- requirements.txt: Python package dependencies for the app.
- scripts/nimbus-aws.yaml: AWS CloudFormation template for creating the infrastructure needed to host the app on EC2.
- notebooks (filings.ipynb, news.ipynb, stock_price_ratings.ipynb): exploratory analysis files used to prototype and test the data workflows before building the final app.

The app links together through a straightforward flow:

1. The user enters a stock ticker in the Streamlit interface.
2. app.py calls the data functions in analysis.py.
3. analysis.py retrieves data from Yahoo Finance using yfinance.
4. The results are displayed in the dashboard as tables, metrics, and informational output.

The AWS deployment template creates the network and EC2 hosting environment, while the app itself continues to run as a Streamlit service on the instance.

## 3. Requirements and installation guide

### Requirements

This project uses the following core dependencies:

- Python 3.14 (recommended for this project environment)
- Streamlit
- pandas
- plotly
- yfinance
- git
- AWS account access for CloudFormation deployment (optional for local use)

### Local setup with a virtual environment

For an offline demo or local development, use a Python virtual environment to isolate dependencies and avoid system-wide package conflicts.

From the project root, run:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This creates an isolated environment for the project and installs the required packages inside it.

### Offline demo guidance

For an offline or classroom demonstration:

- Keep the app local to the machine.
- Use the virtual environment for dependency isolation.
- Avoid relying on external cloud services when demonstrating the app locally.
- Run the app directly from the project root using the local Streamlit server.

### AWS setup with CloudFormation YAML

The project includes a CloudFormation template for AWS deployment in the scripts folder:

- scripts/nimbus-aws.yaml

This template is intended to deploy the app on an EC2 instance in us-east-1 and configures the networking and security settings required for the app to be accessible from the internet.

Recommended AWS deployment process:

1. Log in to the AWS Management Console.
2. Open CloudFormation in the us-east-1 region.
3. Choose Create stack.
4. Upload the template file from scripts/nimbus-aws.yaml.
5. Review the parameters, including the EC2 key pair and GitHub repository URL.
6. Launch the stack and wait for the infrastructure to be created.
7. Once the EC2 instance is running, access the published app URL on port 8501.

This setup is useful for learning AWS networking and EC2 hosting in a classroom environment.

## 4. Instructions on how to run the app

### Run locally

After activating the virtual environment and installing dependencies, start the app from the project root:

```bash
. .venv/bin/activate
streamlit run src/app.py
```

The terminal will provide a local URL, usually on port 8501. Open that URL in your browser to use the app.

### Run with explicit host and port settings

For a remote or cloud-hosted environment, the app should be started with the following configuration:

```bash
. .venv/bin/activate
python -m streamlit run src/app.py --server.address 0.0.0.0 --server.port 8501
```

This makes the app listen on all interfaces and port 8501, which is required for accessibility from outside the local machine.

## 5. Credits and course information

### Credits

Team Members: Wei Zihao, Paavas Bansal, Nicolyne Tiana Lie

### Course

DS600 Cloud Computing for Economics, SMU MDSE

## Notes

This project is a practical example of how data-driven web applications can be built with Python, Streamlit, and cloud infrastructure. It is well suited for use in a teaching environment where students are learning how to connect data workflows, AWS networking, and cloud-hosted app deployment.
