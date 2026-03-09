package com.mealprepperfriend.backend.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ProtectedController {

    @GetMapping("/protected")
    public String protectedEndpoint() {
        return "You are authenticated";
    }
}
