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

    <p>{{ message }}</p>
  </div>
</template>

<script>
import axios from "axios";

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
      try {
        await axios.post(
          "http://localhost:8080/auth/register",
          {
            firstName: this.firstName,
            lastName: this.lastName,
            email: this.email,
            password: this.password
          },
          { withCredentials: true }
        );

        this.$router.push("/login");
      } catch (err) {
        this.message = "Registration failed";
      }
    }
  }
};
</script>
