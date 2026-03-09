<template>
  <div class="home">
    <h1>MealPrepperFriend</h1>
    <p>Your AI-powered weekly meal planning assistant.</p>

    <div class="buttons">
      <router-link to="/login">Login</router-link>
      <router-link to="/register">Register</router-link>
    </div>
  </div>
</template>

<style>
.home {
  text-align: center;
  margin-top: 80px;
}
.buttons a {
  margin: 10px;
  padding: 10px 20px;
  background: #4caf50;
  color: white;
  border-radius: 6px;
  text-decoration: none;
}
</style>
