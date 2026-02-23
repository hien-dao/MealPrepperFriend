package com.mealprepperfriend.backend.service;

import com.mealprepperfriend.backend.dto.LoginRequest;
import com.mealprepperfriend.backend.dto.RegisterRequest;
import com.mealprepperfriend.backend.dto.UserResponse;

public interface AuthService {

    UserResponse register(RegisterRequest request);

    UserResponse login(LoginRequest request);
}
