import { defineStore } from "pinia";
import axios from "axios";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null,
    checkedSession: false
  }),

  actions: {
    async checkSession() {
      if (this.checkedSession) return; // avoid repeated calls

      try {
        const res = await axios.get("http://localhost:8080/auth/me", {
          withCredentials: true
        });
        this.user = res.data;
      } catch (err) {
        this.user = null;
      }

      this.checkedSession = true;
    },

    setUser(user) {
      this.user = user;
    },

    logout() {
      this.user = null;
      this.checkedSession = false;
    }
  }
});
