# MealPrepperFriend

MealPrepperFriend is an AI‑powered meal‑planning and meal‑prepping web application designed to help users plan their meals for an entire week. It generates personalized meal plans based on dietary preferences, fitness goals, and available ingredients, while also simplifying grocery shopping and nutrition tracking.

## Live Demo

**Project URL:** [nutrition.anuj.io](http://nutrition.anuj.io)

## How to Use the App

### 1. Register
Go to the site and create a new account.

### 2. Log In
Use your email and password to access your dashboard.

### 3. Set Your Goals
On the dashboard, fill in your body stats and fitness goal:
- age
- sex
- height
- current weight
- target weight
- activity level
- goal type

After submission, the app calculates your recommended calories and macros.

### 4. Log Meals
Go to the **Meals** page and:
- search for a food item
- choose a result from the dropdown
- review the nutrition preview
- enter the amount eaten in grams
- choose meal type
- save the meal

### 5. View Daily Totals
Your meals page and dashboard show your daily calories and macro totals so you can keep track of progress.

### 6. Update Goals Anytime
You can return to the dashboard later and update your fitness or nutrition goals whenever needed.





## ✨ Key Features

At its current stage, the application includes:

- user registration and login
- password reset flow
- dashboard with calorie and macro information
- health and fitness goal calculation
- meal logging
- USDA food search and nutrition lookup
- deployed production version on AWS EC2

## Current Features

### User Authentication
Users can:
- create an account
- log in and log out
- reset their password if needed

### Health & Fitness Goals
Users can enter:
- age
- sex
- height
- current weight
- target weight
- activity level
- goal type (lose, maintain, gain)

The system then calculates:
- BMR
- maintenance calories
- target calories
- protein target
- carb target
- fat target

These values are saved and shown on the dashboard.

### Meal Logging
Users can:
- search for foods
- select foods from USDA FoodData Central results
- enter a portion size in grams
- log meals by type
- view their logged meals for the day
- see daily totals for calories and macros

### Dashboard
The dashboard acts as the main page for the user and displays:
- saved goal information
- calorie targets
- macro targets
- today’s meal summary
- progress-related nutrition information

### Consistent UI
The app uses a shared visual style across all implemented pages.  
Current pages include:
- `/register`
- `/login`
- `/dashboard`
- `/forgot-password`
- `/reset-password`
- `/meals`

## Planned Features

The full MealPrepperFriend system is designed to include additional features in future sprints, such as:

- AI-based personalized weekly meal plans
- pantry ingredient input through chatbot/NLP
- shopping list generation
- ingredient price lookup
- recipe favorites
- calendar integration
- notifications/reminders
- allergy and dietary filtering
- analytics and progress tracking


## 🛠️ Tech Stack

### Backend
- Python 3
- Flask

### Deployment
- AWS EC2
- Gunicorn
- systemd

### Frontend
- HTML templates
- shared CSS styling across pages

### **AI Engine**
- Python  
- Machine learning / LLM‑powered recipe and meal‑plan generation  

### **Database**  
- MySQL

### **Integrations**
- USDA FoodData Central API
- Google Calendar / Apple Calendar  
- Nutrition APIs  
- Grocery store APIs  
