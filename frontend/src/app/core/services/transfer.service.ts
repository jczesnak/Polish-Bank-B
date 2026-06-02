import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class TransferService {
  // Pamiętaj, że proxy.conf.json przekieruje /api do Django
  private apiUrl = '/api';

  constructor(private http: HttpClient) {}

  createInternalTransfer(transferData: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/internal/`, transferData);
  }
}