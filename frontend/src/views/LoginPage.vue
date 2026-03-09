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
      try {
        const response = await axios.post(
          "http://localhost:8080/auth/login",
          {
            email: this.email,
            password: this.password
          },
          { withCredentials: true }
        );

        this.$router.push("/dashboard");
      } catch (err) {
        this.message = "Login failed";
      }
    }
  }
};
</script>
