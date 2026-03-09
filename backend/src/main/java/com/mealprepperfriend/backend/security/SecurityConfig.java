package com.mealprepperfriend.backend.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;

import com.mealprepperfriend.backend.repository.UserRepository;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {

        http
            // CSRF: enabled, token stored in cookie for SPA
            .csrf(csrf -> csrf
                .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse())
            )

            // AUTH RULES
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/auth/register", "/auth/login").permitAll()
                .anyRequest().authenticated()
            )

            // DISABLE FORM LOGIN + BASIC AUTH
            .formLogin(form -> form.disable())
            .httpBasic(basic -> basic.disable())

            // LOGOUT handled by Spring Security at /auth/logout
            .logout(logout -> logout
                .logoutUrl("/auth/logout")
                .invalidateHttpSession(true)
                .deleteCookies("JSESSIONID")
                .permitAll()
            )

            // SESSION CREATION
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED)
            );

        return http.build();
    }

    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration config) throws Exception {
        return config.getAuthenticationManager();
    }

    @Bean
    public UserDetailsService userDetailsService(UserRepository userRepository) {
        return email -> {
            // Fully qualify your entity class to avoid conflict
            com.mealprepperfriend.backend.model.User entityUser =
                    userRepository.findByEmail(email)
                        .orElseThrow(() -> new UsernameNotFoundException("User not found"));

            // Use Spring Security's User class (imported normally)
            return org.springframework.security.core.userdetails.User
                    .withUsername(entityUser.getEmail())
                    .password(entityUser.getPassword())
                    .roles(entityUser.getRole().name())
                    .build();
        };
    }


}
