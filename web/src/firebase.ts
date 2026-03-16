import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyDvxfBSGq4GfFTXhnEZZn5rQb3c0GwZKqo",
  authDomain: "tokreducer.firebaseapp.com",
  projectId: "tokreducer",
  storageBucket: "tokreducer.firebasestorage.app",
  messagingSenderId: "374567401962",
  appId: "1:374567401962:web:62f206856f233777195a93",
  measurementId: "G-8PS83N4100",
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
