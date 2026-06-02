import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap, catchError, throwError } from 'rxjs';

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  pesel: string;
  role: 'PARENT' | 'JUNIOR';
}

interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface LoginData {
  email: string;
  password: string;
}

export interface RegisterData {
  pesel: string;
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
  password: string;
  password_confirm: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly API = '/api';

  private _user = signal<User | null>(this.loadUser());
  readonly user = this._user.asReadonly();
  readonly isAuthenticated = computed(() => !!this._user());

  constructor(private http: HttpClient, private router: Router) {}

  login(data: LoginData) {
    return this.http.post<AuthResponse>(`${this.API}/auth/login/`, data).pipe(
      tap((res) => this.handleAuthSuccess(res)),
      catchError((err) => throwError(() => err)),
    );
  }

  register(data: RegisterData) {
    return this.http.post<AuthResponse>(`${this.API}/auth/register/`, data).pipe(
      tap((res) => this.handleAuthSuccess(res)),
      catchError((err) => throwError(() => err)),
    );
  }

  logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    this._user.set(null);
    this.router.navigate(['/auth/login']);
  }

  getAccessToken(): string | null {
    return localStorage.getItem('access_token');
  }

  private handleAuthSuccess(res: AuthResponse) {
    localStorage.setItem('access_token', res.access);
    localStorage.setItem('refresh_token', res.refresh);
    localStorage.setItem('user', JSON.stringify(res.user));
    this._user.set(res.user);
    this.router.navigate([res.user.role === 'JUNIOR' ? '/junior-dashboard' : '/dashboard']);
  }

  private loadUser(): User | null {
    try {
      const raw = localStorage.getItem('user');
      return raw ? (JSON.parse(raw) as User) : null;
    } catch {
      return null;
    }
  }
}
