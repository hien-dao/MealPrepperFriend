package com.mealprepperfriend.backend.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import com.mealprepperfriend.backend.dto.LoginRequest;
import com.mealprepperfriend.backend.dto.RegisterRequest;
import com.mealprepperfriend.backend.dto.UserResponse;
import com.mealprepperfriend.backend.repository.UserRepository;

@SpringBootTest
@Transactional
@ActiveProfiles("test")
class AuthServiceImplTest {

    @Autowired
    private AuthService authService;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    private RegisterRequest registerRequest;

    @BeforeEach
    void setup() {
        registerRequest = new RegisterRequest();
        registerRequest.setFirstName("John");
        registerRequest.setLastName("Doe");
        registerRequest.setEmail("john@example.com");
        registerRequest.setPassword("123456");
    }

    @Test
    void testRegisterSuccess() {
        UserResponse response = authService.register(registerRequest);

        assertNotNull(response.getId());
        assertEquals("john@example.com", response.getEmail());
        assertEquals("John", response.getFirstName());
        assertEquals("Doe", response.getLastName());

        assertTrue(userRepository.findByEmail("john@example.com").isPresent());
    }

    @Test
    void testRegisterDuplicateEmail() {
        authService.register(registerRequest);

        assertThrows(RuntimeException.class, () -> {
            authService.register(registerRequest);
        });
    }

    @Test
    void testLoginSuccess() {
        authService.register(registerRequest);

        LoginRequest login = new LoginRequest();
        login.setEmail("john@example.com");
        login.setPassword("123456");

        UserResponse response = authService.login(login);

        assertEquals("john@example.com", response.getEmail());
    }

    @Test
    void testLoginWrongPassword() {
        authService.register(registerRequest);

        LoginRequest login = new LoginRequest();
        login.setEmail("john@example.com");
        login.setPassword("wrongpass");

        assertThrows(RuntimeException.class, () -> {
            authService.login(login);
        });
    }

    @Test
    void testLoginUnknownEmail() {
        LoginRequest login = new LoginRequest();
        login.setEmail("unknown@example.com");
        login.setPassword("123456");

        assertThrows(RuntimeException.class, () -> {
            authService.login(login);
        });
    }
}
