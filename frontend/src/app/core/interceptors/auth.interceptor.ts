import { HttpInterceptorFn, HttpErrorResponse, HttpBackend, HttpClient } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const backend = inject(HttpBackend);

  const token = auth.getAccessToken();
  const authReq = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authReq).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status !== 401 || req.url.includes('/token/refresh/')) {
        return throwError(() => error);
      }

      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        auth.logout();
        return throwError(() => error);
      }


      const http = new HttpClient(backend);
      return http.post<{ access: string }>('/api/auth/token/refresh/', { refresh: refreshToken }).pipe(
        switchMap((res) => {
          localStorage.setItem('access_token', res.access);
          const retried = req.clone({ setHeaders: { Authorization: `Bearer ${res.access}` } });
          return next(retried);
        }),
        catchError(() => {
          auth.logout();
          return throwError(() => error);
        }),
      );
    }),
  );
};
