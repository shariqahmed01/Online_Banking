package com.example.bank_backend.Controller;

import com.example.bank_backend.Model.LoginPO;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class Authentication {
    @PostMapping("/authLogin")
    public String test(@RequestBody LoginPO loginPO){
        return loginPO.toString();
    }
}
