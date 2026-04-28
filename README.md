🌿 Nourish — AI-Powered Nutrition & Fitness Tracker
--------------------------------------------------
A full-stack web app for tracking nutrition, workouts, hydration, and meal planning — with an AI assistant built in.

Live at: https://nutrition.anuj.io

Stack: Python · Flask · MySQL · Gunicorn · AWS EC2 · OpenAI GPT-4o · USDA FoodData Central

Table of Contents
-----------------
- Getting Started
- Features
- Dashboard
- Meal Log
- Meal Planner
- Meal Calendar
- Community Forum
- Progress & Goals
- Hydration Tracker
- Workout Tracker
- Nouri AI Assistant
- Notifications
- Pricing & Premium
- Tech Stack
- Project Structure

Getting Started
---------------

1. Register an account
----------------------

Go to /register and create an account with your email and password. You'll receive a verification email — click the link to activate your account.

2. Set your goals
-----------------

After logging in, head to Progress in the sidebar. Fill in your current stats (age, sex, height, weight, activity level) and your goal (lose / maintain / gain weight). Nourish will calculate your daily calorie and macro targets using the Mifflin-St Jeor formula.

3. Start tracking
-----------------

Once your goals are set, use the sidebar to navigate to any feature. The Dashboard gives you a daily overview — start there.

Features
--------

Dashboard
---------

The dashboard is your daily hub. It shows:
- Greeting banner with your current logging streak
- Today's meals — everything you've logged today at a glance
- Calorie progress — how close you are to your daily target
- Weekly calorie chart — a 7-day bar chart of your intake
- Weekly stats — total calories, protein, carbs, fat, and meals logged this week
- Recent days — quick summary of the past 3 days
- Goals summary — your current calorie and macro targets with a link to the full Progress page
- Recipe ideas — 3 random recipe suggestions from the database, each with a "Cook this →" button that opens the Meal Planner pre-filled with that dish

Meal Log
--------

Navigate to Meal Log (/meals) to log what you eat.

Searching for food:
- Type any food name into the search bar — powered by the USDA FoodData Central database
- Select from the autocomplete results
- Choose a meal type (Breakfast, Lunch, Dinner, Snack)
- Enter the portion in grams — the app scales all macros to your portion size

What gets tracked per meal:
- Calories, Protein (g), Carbohydrates (g), Fat (g)
- Food name, meal type, date, portion size

Daily totals are shown below the log form, updating as you add meals.

Meal Planner
------------

Navigate to Meal Planner (/planner) to plan what to cook.

Getting an ingredient list:
1. Type any dish or meal idea (e.g. "butter paneer masala", "grilled salmon with asparagus")
2. Click Get Ingredients →
3. GPT-4o generates a structured ingredient list with quantities, units, and estimated US grocery prices (Walmart/Kroger level)
4. Check or uncheck ingredients you already have
5. A running cost total updates as you select/deselect

Getting a recipe:
- After loading ingredients, click 📖 Get Recipe
- GPT-4o-mini generates a concise step-by-step recipe using those ingredients
- The recipe appears inline below the ingredient grid

Saving to calendar:
- After getting a recipe, pick a date using the date picker
- Click Save to Calendar → to pin the recipe to that date
- View it later on the Meal Calendar page

Search history — your last 5 searches are shown in the sidebar for quick re-access.

Meal Calendar
-------------

Navigate to Calendar (/calendar) to see your planned meals by date.
- Month view — a full monthly grid showing all your pinned recipes
- Recipe chips — each pinned recipe appears as a chip on its date
- Click a chip to open a detail modal showing the dish name, date, and full ingredient list
- Remove entries by clicking the ✕ on any chip
- Navigate months using the ← → arrows at the top
- Today's date is highlighted in green
- Click + Plan a Meal to jump to the Meal Planner

Recipes are pinned from the Meal Planner page using the "Save to Calendar" button after generating a recipe.

Community Forum
---------------

Navigate to Community (/forum) to share and discover.

Anyone can read — the forum is publicly visible, no login required.

Post types:
- General — share thoughts, ask questions, post tips
- Recipe — a special post type with structured nutrition fields (calories, protein, carbs, fat per serving) and an ingredient list, displayed as a formatted nutrition card

Post features:
- Title, body text (up to 10,000 characters)
- Optional photo upload (any post type)
- Category tags: Recipe, Nutrition, Fitness, General, Question, Tips

Interaction:
- Upvote posts (toggle on/off, logged-in users only)
- Comments with threaded replies (one level deep)
- Delete your own posts

Filtering — use the category pills at the top to filter by topic.

Progress & Goals
----------------

Navigate to Progress (/progress) for your full health dashboard.

Nutrition targets — shows your computed daily calorie and macro goals, goal type badge (Lose / Maintain / Gain), and a progress bar toward your target weight.

Workout activity summary:
- Sessions this week
- Sessions this month
- Last session name, date, and exercise count with a direct link

Body weight log:
- Log your weight for any date (defaults to today)
- Optional note per entry
- Last 5 entries shown inline
- Weight trend chart (Canvas-based) plotting your last 30 days with a target weight line

Goals edit form — always visible below the summary. Fill in your stats and click Update Goals to recalculate everything. Every save is snapshotted to the goals history table.

Goals history table — shows every time you've updated your goals, with the date, goal type, weight, target, calories, and protein.

Hydration Tracker
-----------------

Navigate to Hydration (/water) to track your daily water intake.

Quick add buttons — one click to log 250ml, 350ml, 500ml, or 1 glass (250ml).

Custom amount — enter any amount and choose ml or glasses from the unit dropdown.

Daily progress circle — an SVG donut showing how much of your daily goal you've reached. Turns green when you hit your target.

Today's entries — every log entry shown with the time it was added and a ✕ to remove it.

Daily goal — set your target in ml (default 2000ml). Updates instantly.

Weekly bar chart — 7-day history of your daily intake. Bars turn green on days you hit your goal.

Workout Tracker
---------------

Navigate to Workout (/workout) to log your training sessions.

Creating a session:
1. Give the session a name (e.g. "Push Day", "Morning Run")
2. Pick a date (defaults to today)
3. Add an optional note
4. Click Start session →

Adding exercises (inside a session at /workout/session/<id>):
- Toggle between 💪 Strength and 🏃 Cardio mode
- Strength: enter exercise name, sets, reps, weight (kg)
- Cardio: enter exercise name, duration (minutes), distance (km)
- Average pace (km/h) is calculated automatically for cardio

Calorie estimation:
- After adding exercises, click ✦ Estimate Calories
- A single GPT-4o-mini call estimates calories for the whole session and each individual exercise
- Results are cached — click ↺ Recalculate if you add more exercises
- Each exercise card shows its estimated calorie burn in the top-right corner

Nouri AI Assistant
------------------

The Nouri chatbot bubble (🌿) is available on every page. Click it to open.

What Nouri can do:
- Answer nutrition and fitness questions
- Log meals conversationally ("I just had 150g of oats and a banana")
- Suggest recipes based on what you have in your fridge
- Give advice based on your goals and today's meals

Free plan: 10 messages per 3-hour window.

Pro plan: Unlimited messages + page context awareness.

Page context (Pro only): When you're on a specific page, Nouri automatically knows what you're looking at:
- On the Meal Planner — knows the current recipe and ingredients
- On the Workout session page — knows your exercises
- On the Progress page — knows your goals and recent weight
- On other pages — knows general page context

This means you can ask "can I substitute the paneer in this recipe?" or "was today's workout enough cardio?" without explaining anything.

Rate limit — free users see a clear message when they hit the limit with a link to upgrade.

Notifications
-------------

Navigate to Notifications (/notifications) to set up reminders.

Scheduled notifications — fire at a specific time on selected days of the week:
1. Enter a title and message
2. Pick a time
3. Select which days (Mon–Sun, all checked by default)
4. Click Create Reminder →

The app checks for due notifications every 60 seconds while you're on the site and shows an in-app popup. If you've granted browser push notification permission, it also fires a native push notification.

Periodic notifications — repeat on a fixed interval while you're on the site:
- Enter a title, message, and interval in minutes (minimum 5)
- JS timers start on page load and repeat until you close the tab

Quick presets — one-click setup for common reminders:
- 💧 Drink Water (every 30 min)
- 👁️ Screen Break (every 20 min)
- 🚶 Take a Walk (every 60 min)
- 🍽️ Log Your Meal (daily at 1 PM)

Toggle on/off — pause any reminder without deleting it using the toggle switch.

Delete — remove reminders with the ✕ button.
Note: Periodic reminders reset when you refresh or navigate to a new page since they run as JS timers. Scheduled reminders are DB-backed and persist across sessions.

Pricing & Premium
-----------------

Navigate to Pricing (/pricing) to compare plans.

Feature | Free | Pro ($9.99/mo)
Meal logging | ✓ | ✓
Calorie & macro tracking | ✓ | ✓
Water tracker | ✓ | ✓
Workout tracker | ✓ | ✓
Progress & goals | ✓ | ✓
Meal planner | ✓ | ✓
Community forum | ✓ | ✓
Nouri AI queries | 10/day | Unlimited
Nouri page context | ✗ | ✓
Live Kroger grocery prices | ✗ | ✓

Demo toggle — for demonstration purposes, you can toggle your account between Free and Pro using the button in the sidebar. No real payment is processed.

Tech Stack
----------

Layer: Technology
Backend: Python 3.9, Flask, Gunicorn
Database: MySQL (AWS RDS)
Frontend: Jinja2 templates, vanilla JS, Canvas API
AI: OpenAI GPT-4o (chat, planner), GPT-4o-mini (recipes, calorie estimation)
Food data: USDA FoodData Central API
Grocery prices: Kroger API
Hosting: AWS EC2 (Amazon Linux)
Domain: AWS Route53
Auth: bcrypt password hashing, Flask sessions, email verification

Project Structure
-----------------

usermgmt/

├── app.py - Main Flask app, auth, dashboard, chat routes

├── goals.py - FR-10 goals, macros, weight logging, dashboard helpers

├── forum.py - Community forum — posts, comments, upvotes

├── planner.py - Meal planner, ingredient generation, recipe generation

├── calendar_bp.py - Meal calendar — save and view recipes by date

├── water.py - Hydration tracking

├── workout.py - Workout sessions, exercises, calorie estimation

├── notifications.py - Scheduled and periodic notifications

├── seed_recipes.py - Seeds 50 healthy recipes into the DB

│

├── templates/

│ ├── partials/

│ │ ├── navbar.html - Sidebar navigation (desktop + mobile)

│ │ └── chat.html - Nouri chatbot bubble + global notification popup

│ ├── dashboard.html

│ ├── meals.html

│ ├── planner.html

│ ├── calendar.html

│ ├── forum.html

│ ├── forum_post.html

│ ├── goals_page.html - /progress page

│ ├── water.html

│ ├── workout.html

│ ├── workout_session.html

│ ├── notifications.html

│ ├── pricing.html

│ ├── register.html

│ ├── login.html

│ └── forgot_password.html

│

└── static/

 └── uploads/

 └── forum/ - User-uploaded forum images

Environment Variables
---------------------

The app requires the following environment variables (set in the systemd service file on EC2):

DB_HOST
DB_USER
DB_PASS
DB_NAME
FLASK_SECRET_KEY
OPENAI_API_KEY
USDA_API_KEY
KROGER_CLIENT_ID
KROGER_CLIENT_SECRET
BASE_URL
EMAIL_MODE

Built as a Software Engineering project — Group 7, Spring 2026.
