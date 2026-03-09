import { createRouter, createWebHistory } from "vue-router";
import axios from "axios";
import { useAuthStore } from "../store/auth";

import HomePage from "../views/HomePage.vue";
import LoginPage from "../views/LoginPage.vue";
import RegisterPage from "../views/RegisterPage.vue";
import DashboardPage from "../views/DashboardPage.vue";

const routes = [
  { path: "/", name: "home", component: HomePage },

  { path: "/login", name: "login", component: LoginPage },
  { path: "/register", name: "register", component: RegisterPage },

  {
    path: "/dashboard",
    name: "dashboard",
    component: DashboardPage,
    meta: { requiresAuth: true }
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore();

  // Check session only once per page load
  await auth.checkSession();

  if (to.meta.requiresAuth && !auth.user) {
    return next("/login");
  }

  next();
});

export default router;