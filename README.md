# 🚀 Streamlit NYC Taxi App Deployment on AWS Elastic Beanstalk

---

## ⚡ BEFORE DOING ANY STEPS, SET UP THE FOLLOWING:

1. **Find your SageMaker Execution Role**  
   - Go to AWS Console → SageMaker → Notebook instances → Select your instance → Copy the **Execution Role ARN**.

2. **Add AdministratorAccess-AWSElasticBeanstalk**  
   - Attach the IAM Policy `AdministratorAccess-AWSElasticBeanstalk` to your SageMaker execution role.

3. **Install AWS Elastic Beanstalk CLI**  
   Run the following command:
   ```bash
   pip install awsebcli --no-cache
4 **Check Permissions:**

  Make sure your IAM role/user has permissions for:

      Elastic Beanstalk
      
      EC2
      
      S3
      
      IAM Role creation
      
      CloudFormation

## 🛠️ Set Up Local Development Environment

### Step 1: Navigate to the Project Directory

```cd streamlit-eb```

### Step 2: Create and Activate a Virtual Environment

```python3 -m venv .venv
source .venv/bin/activate     # On Linux/Mac
# OR
.venv\Scripts\activate        # On Windows
```
### Step 3: Install Required Python Libraries

```pip install -r requirements.txt```


### Step 4 (Optional): Run Streamlit App Locally

```streamlit run app.py```

## 🚀 How to Deploy the Application on AWS Elastic Beanstalk

### Step 1: Initialize Elastic Beanstalk

eb init

### Step 2: Create a New Environment
eb create streamlit-env2 ((Note: streamlit-env2 is just an example name. You can choose any environment name you like.)

### Step 3: Deploy the Application
eb deploy

### Step 4: Open the Deployed Application
eb open



