package com.example.bank_backend.Model;

import org.springframework.stereotype.Component;

@Component
public class LoginPO {
    String username;
    String password;

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    @Override
    public String toString() {
        return "LoginPO{" +
                "username='" + username + '\'' +
                ", password='" + password + '\'' +
                '}';
    }
}
