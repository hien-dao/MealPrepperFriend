<template>
  <div class="dashboard">
    <h1>Welcome to your Dashboard</h1>
    <p>You are logged in!</p>

    <button @click="logout">Logout</button>
  </div>
</template>

<script>
import axios from "axios";
import { useAuthStore } from "../store/auth";

export default {
  methods: {
    async logout() {
      const auth = useAuthStore();

      try {
        await axios.post(
          "http://localhost:8080/auth/logout",
          {},
          { withCredentials: true }
        );
      } catch (err) {
        // Even if backend fails, still clear local state
      }

      // Clear Pinia auth state
      auth.logout();

      // Redirect to homepage
      this.$router.push({ name: "home" });
    }
  }
};
</script>
