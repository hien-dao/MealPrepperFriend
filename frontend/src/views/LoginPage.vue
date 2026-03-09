<template>
  <div class="login">
    <h2>Login</h2>

    <form @submit.prevent="login">
      <input v-model="email" placeholder="Email" type="email" required />
      <input v-model="password" placeholder="Password" type="password" required />

      <button type="submit">Login</button>
    </form>

    <p>{{ message }}</p>
  </div>
</template>

<script>
import axios from "axios";
import { useAuthStore } from "../store/auth";

export default {
  data() {
    return {
      email: "",
      password: "",
      message: ""
    };
  },
  methods: {
    async login() {
      const auth = useAuthStore();

      try {
        const response = await axios.post(
          "http://localhost:8080/auth/login",
          {
            email: this.email,
            password: this.password
          },
          { withCredentials: true }
        );

        // Save user in Pinia store
        auth.setUser(response.data);

        this.$router.push({ name: "dashboard" });
      } catch (err) {
        this.message = "Login failed";
      }
    }
  }
};
</script>
