<template>
  <div class="register">
    <h2>Create Account</h2>

    <form @submit.prevent="register">
      <input v-model="firstName" placeholder="First Name" required />
      <input v-model="lastName" placeholder="Last Name" required />
      <input v-model="email" placeholder="Email" type="email" required />
      <input v-model="password" placeholder="Password" type="password" required />

      <button type="submit">Register</button>
    </form>

    <p v-if="message" class="error">{{ message }}</p>
  </div>
</template>

<script>
import axios from "axios";
import { useAuthStore } from "../store/auth";

export default {
  data() {
    return {
      firstName: "",
      lastName: "",
      email: "",
      password: "",
      message: ""
    };
  },
  methods: {
    async register() {
      this.message = "";
      const auth = useAuthStore();

      try {
        const response = await axios.post(
          "http://localhost:8080/auth/register",
          {
            firstName: this.firstName,
            lastName: this.lastName,
            email: this.email,
            password: this.password
          },
          { withCredentials: true }
        );

        // Save user in Pinia store
        auth.setUser(response.data);

        this.$router.push({ name: "dashboard" });
      } catch (err) {
        if (err.response && err.response.data) {
          const data = err.response.data;

          if (data.errors) {
            this.message = Object.values(data.errors)[0];
          } else if (data.message) {
            this.message = data.message;
          } else {
            this.message = "Registration failed";
          }
        } else {
          this.message = "Cannot connect to server";
        }
      }
    }
  }
};
</script>

<style>
.error {
  color: red;
  margin-top: 10px;
}
</style>
