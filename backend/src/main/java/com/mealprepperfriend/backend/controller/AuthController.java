package com.mealprepperfriend.backend.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.mealprepperfriend.backend.dto.LoginRequest;
import com.mealprepperfriend.backend.dto.RegisterRequest;
import com.mealprepperfriend.backend.dto.UserResponse;
import com.mealprepperfriend.backend.service.AuthService;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;

@RestController
@RequestMapping("/auth")
public class AuthController {

    private final AuthService authService;
    private final UserDetailsService userDetailsService;

    public AuthController(AuthService authService,
                          UserDetailsService userDetailsService) {
        this.authService = authService;
        this.userDetailsService = userDetailsService;
    }

    @PostMapping("/register")
    public ResponseEntity<UserResponse> register(@Valid @RequestBody RegisterRequest request) {
        UserResponse response = authService.register(request);
        return ResponseEntity.ok(response);
    }

    @PostMapping("/login")
    public ResponseEntity<UserResponse> login(@Valid @RequestBody LoginRequest request,
                                              HttpServletRequest httpRequest) {

        // 1. Let service validate credentials (no duplication)
        UserResponse response = authService.login(request);

        // 2. Load UserDetails for Spring Security
        UserDetails userDetails = userDetailsService.loadUserByUsername(request.getEmail());

        // 3. Create Authentication and store in SecurityContext
        UsernamePasswordAuthenticationToken authToken =
                new UsernamePasswordAuthenticationToken(
                        userDetails,
                        null,
                        userDetails.getAuthorities()
                );

        SecurityContextHolder.getContext().setAuthentication(authToken);

        // 4. Ensure session is created
        httpRequest.getSession(true);

        return ResponseEntity.ok(response);
    }

    // REMOVE the /logout endpoint here.
    // Spring Security handles POST/GET to /auth/logout as configured in SecurityConfig.
}
