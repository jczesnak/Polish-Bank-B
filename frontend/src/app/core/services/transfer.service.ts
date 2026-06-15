import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class TransferService {

  private apiUrl = '/api/transfers'; 

  constructor(private http: HttpClient) {}

  createInternalTransfer(transferData: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/internal/`, transferData);
  }
}