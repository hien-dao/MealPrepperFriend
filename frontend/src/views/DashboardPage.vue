<template>
  <div class="dashboard">
    <h1>Welcome to your Dashboard</h1>
    <p>You are logged in!</p>

    <button @click="logout">Logout</button>
  </div>
</template>

<script>
import axios from "axios";

export default {
  methods: {
    async logout() {
      await axios.post("http://localhost:8080/auth/logout", {}, { withCredentials: true });
      this.$router.push("/");
    }
  }
};
</script>
