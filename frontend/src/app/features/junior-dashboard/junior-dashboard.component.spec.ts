import { ComponentFixture, TestBed } from '@angular/core/testing';

import { JuniorDashboardComponent } from './junior-dashboard.component';

describe('JuniorDashboardComponent', () => {
  let component: JuniorDashboardComponent;
  let fixture: ComponentFixture<JuniorDashboardComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [JuniorDashboardComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(JuniorDashboardComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
