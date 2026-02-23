# MealPrepperFriend

MealPrepperFriend is an AI‑powered meal‑planning and meal‑prepping web application designed to help users plan their meals for an entire week. It generates personalized meal plans based on dietary preferences, fitness goals, and available ingredients, while also simplifying grocery shopping and nutrition tracking.

## 🏃 How to Run the Project (Without Using an IDE)
### 1. Requirements
- Java 21+
- Maven Wrapper (included in `/backend`)
- Node.js 18+
- npm (comes with Node)
- MySQL 8+ (local installation **or** AWS RDS MySQL instance)
### 2. Database Setup
- Update credentials in `/backend/src/main/resources/application.yml`
- Create the database:
   ```sql
   CREATE DATABASE mealprepperfriend;
   ```
### 3. Run the Project
- Backend will start at `http://localhost:8080`
  ```
  cd backend
  ./mvnw spring-boot:run
  ```
- Frontend will start at `http://localhost:5173`
  ```
  cd frontend
  npm install
  npm run dev
  ```



## ✨ Key Features

- **AI Chatbot Ingredient Input**  
  Enter ingredients you already have and receive instant recipe suggestions.

- **Calories & Macros Calculator**  
  Personalized nutrition breakdowns based on fitness and health goals.

- **Smart Recipe Suggestions**  
  Categorized recipes, favourites, weekly plan editing, and goal‑based recommendations.

- **Calendar Integration**  
  Sync meal plans with Google or Apple Calendar.

- **Auto‑Generated Shopping List**  
  Create a complete shopping list for the week.

- **Ingredient Price Fetching**  
  Pull pricing data from nearby or online stores.

- **Personalized Nutrition Targets**  
  Body composition + athleticism + health goals → nutrient goals → recipe generation.

- **Allergy & Preference Filters**  
  Exclude meals based on allergies, religion, or personal preferences.

- **Analytics Dashboard**  
  Track progress, habits, and nutritional trends.

- **Community Recipes**  
  Submit recipes and add others’ recipes to your personal recipe book.

- **User Accounts**  
  Log in/out, manage account info, and personalize health data (e.g., heart rate).

## 🛠️ Tech Stack

### **Frontend**
- Vue.js

### **Backend**
- Java  
- Spring Boot

### **AI Engine**
- Python  
- Machine learning / LLM‑powered recipe and meal‑plan generation  

### **Database**  
- MySQL

### **Integrations**
- Google Calendar / Apple Calendar  
- Nutrition APIs  
- Grocery store APIs  
