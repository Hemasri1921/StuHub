import os
import unittest
import random
import time
import uuid
import sqlite3
from werkzeug.security import generate_password_hash
from app import app, get_db

class StuHubCompleteTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

        # Ensure demo student and admin exist, are verified, and event 1 is Open
        with app.app_context():
            db = get_db()
            cursor = db.cursor()
            cursor.execute("UPDATE users SET name = 'Rahul Sharma', email_verified = 1 WHERE email = 'rahul@stuhub.edu'")
            cursor.execute("UPDATE users SET email_verified = 1 WHERE email = 'admin@stuhub.edu'")
            cursor.execute("UPDATE events SET status = 'Open' WHERE id = 1")
            db.commit()

    def test_01_landing_page(self):
        """Verify clean modern Landing page hero, tagline, and minimal features."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'STUHUB', response.data)
        self.assertIn(b'Student Support Portal', response.data)
        self.assertIn(b'Get Started', response.data)
        self.assertIn(b'Explore Features', response.data)
        self.assertIn(b'Campus Services', response.data)
        self.assertIn(b'Complaints', response.data)
        # Verify removed clutter is absent
        self.assertNotIn(b'One Platform. Everything Students Need.', response.data)
        self.assertNotIn(b'All-in-One Campus Support Portal', response.data)
        self.assertNotIn(b'100% Campus Verified', response.data)

    def test_02_login_page_renders_and_validates(self):
        """Verify Login page loads and rejects invalid credentials."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome Back', response.data)

        # Invalid login
        bad_res = self.client.post('/login', data={
            'identifier': 'fake@stuhub.edu',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        self.assertIn(b'Invalid college email or password', bad_res.data)

    def test_03_login_student_and_admin(self):
        """Verify student demo login and admin demo login."""
        # Student Login
        stu_res = self.client.post('/login', data={
            'identifier': 'rahul@stuhub.edu',
            'password': 'student123'
        }, follow_redirects=True)
        self.assertEqual(stu_res.status_code, 200)
        self.assertIn(b'Welcome back, Rahul Sharma!', stu_res.data)

        # Logout student
        self.client.get('/logout')

        # Admin Login
        admin_res = self.client.post('/login', data={
            'identifier': 'admin@stuhub.edu',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertEqual(admin_res.status_code, 200)
        self.assertIn(b'Campus Administration Portal', admin_res.data)

    def test_04_register_all_branches(self):
        """Verify student registration with multi-branch support and college email verification."""
        branches_to_test = ['Mechanical', 'Civil', 'AI & DS', 'AI & ML', 'ECE', 'EEE', 'IT', 'CSE']
        test_branch = random.choice(branches_to_test)
        unique_suffix = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
        test_email = f"student_{unique_suffix}@stuhub.edu"

        # Request verification code
        send_res = self.client.post('/api/send-verification-code', json={'email': test_email})
        self.assertEqual(send_res.status_code, 200)
        dev_code = send_res.get_json()['dev_code']

        # Verify code
        ver_res = self.client.post('/api/verify-code', json={'email': test_email, 'code': dev_code})
        self.assertEqual(ver_res.status_code, 200)
        self.assertIn('Email Verified Successfully', ver_res.get_json()['message'])
        
        response = self.client.post('/register', data={
            'name': f'Kavya Patel {unique_suffix[:6]}',
            'roll_number': f'22{test_branch[:3].upper()}{unique_suffix[:6]}',
            'branch': test_branch,
            'year': '2nd Year',
            'email': test_email,
            'phone': '9876543210',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Registration successful', response.data)

    def test_05_student_dashboard_four_cards_and_personal_activity(self):
        """Verify student dashboard displays EXACTLY 4 main feature cards and JUST YOUR ACTIVITY."""
        self.client.post('/login', data={'identifier': 'rahul@stuhub.edu', 'password': 'student123'})
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome back, Rahul Sharma!', response.data)
        
        # 4 Main Cards
        self.assertIn(b'LOST &amp; FOUND ITEMS', response.data)
        self.assertIn(b'COMPLAINTS RAISE', response.data)
        self.assertIn(b'CAMPUS EVENTS', response.data)
        self.assertIn(b'ANNOUNCEMENTS', response.data)

        # Personal Activity Section
        self.assertIn(b'JUST YOUR ACTIVITY', response.data)

    def test_06_complaint_raise_and_notification(self):
        """Verify complaint submission with cleanliness category, date, and notification."""
        self.client.post('/login', data={'identifier': 'rahul@stuhub.edu', 'password': 'student123'})
        response = self.client.post('/complaints', data={
            'category': 'Cleanliness',
            'date': '2026-09-13',
            'location': 'Block C corridor 2nd floor',
            'description': 'Corridor requires floor sweeping and trash can emptying.'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Complaint Submitted Successfully', response.data)

        # Verify notification
        notif_res = self.client.get('/notifications')
        self.assertIn(b'New Complaint Reported', notif_res.data)

    def test_07_lost_and_found_reporting_with_photo_and_notifications(self):
        """Verify Lost & Found reporting routes and exact notification titles."""
        self.client.post('/login', data={'identifier': 'rahul@stuhub.edu', 'password': 'student123'})
        
        # Report lost item with camera photo
        res_lost = self.client.post('/lost', data={
            'item_name': 'Blue Parker Pen',
            'category': 'Other',
            'location': 'Library 1st floor',
            'date': '2026-09-13',
            'contact_details': 'rahul@stuhub.edu'
        }, follow_redirects=True)
        self.assertEqual(res_lost.status_code, 200)
        self.assertIn(b'Lost Item Reported Successfully', res_lost.data)

        # Report found item
        res_found = self.client.post('/found', data={
            'item_name': 'Steel Keychain',
            'category': 'Other',
            'location': 'Cafeteria Table 4',
            'date': '2026-09-13',
            'contact_details': 'security@stuhub.edu'
        }, follow_redirects=True)
        self.assertEqual(res_found.status_code, 200)
        self.assertIn(b'Found Item Reported Successfully', res_found.data)

        # Check notifications
        notif_res = self.client.get('/notifications')
        self.assertIn(b'Reported a Lost Item', notif_res.data)
        self.assertIn(b'Reported a Found Item', notif_res.data)

    def test_08_search_items(self):
        """Verify searching items across categories and locations."""
        self.client.post('/login', data={'identifier': 'rahul@stuhub.edu', 'password': 'student123'})
        response = self.client.get('/search?q=Calculator')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Calculator', response.data)

    def test_09_campus_events_two_options_landing(self):
        """Verify Campus Events landing FIRST displays ONLY TWO grand options: Technical and Non-Technical."""
        self.client.post('/login', data={'identifier': 'rahul@stuhub.edu', 'password': 'student123'})
        response = self.client.get('/events')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Campus Events Portal', response.data)
        self.assertIn(b'TECHNICAL', response.data)
        self.assertIn(b'Technical competitions, hackathons, coding events, workshops and academic activities.', response.data)
        self.assertIn(b'NON-TECHNICAL', response.data)
        self.assertIn(b'Cultural, creative, sports and other student activities.', response.data)

    def test_09b_campus_events_stream_filtering(self):
        """Verify Technical and Non-Technical event stream filtering."""
        self.client.post('/login', data={'identifier': 'rahul@stuhub.edu', 'password': 'student123'})
        
        # Technical stream
        tech_res = self.client.get('/events?category=Technical')
        self.assertEqual(tech_res.status_code, 200)
        self.assertIn(b'Technical Events', tech_res.data)
        self.assertIn(b'Hackathons', tech_res.data)

        # Non-Technical stream
        non_tech_res = self.client.get('/events?category=Non-Technical')
        self.assertEqual(non_tech_res.status_code, 200)
        self.assertIn(b'Non-Technical Events', non_tech_res.data)
        self.assertIn(b'Dancing', non_tech_res.data)

    def test_10_free_event_registration(self):
        """Verify Free event registration generates unique ID and confirmed pass."""
        rnd = random.randint(10000, 99999)
        test_email = f"student_evt{rnd}@stuhub.edu"

        # Verify email first
        s_res = self.client.post('/api/send-verification-code', json={'email': test_email})
        self.assertEqual(s_res.status_code, 200)
        d_code = s_res.get_json()['dev_code']
        self.client.post('/api/verify-code', json={'email': test_email, 'code': d_code})

        self.client.post('/register', data={
            'name': 'Pooja Hegde',
            'roll_number': f'22CSE{rnd}',
            'branch': 'CSE',
            'year': '3rd Year',
            'email': test_email,
            'phone': '9876543210',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)

        # Free event registration (Event 1: Hackathon)
        response = self.client.post('/events/1/register', data={
            'student_name': 'Pooja Hegde',
            'roll_number': f'22CSE{rnd}',
            'branch': 'Computer Science',
            'year': '3rd Year',
            'email': test_email,
            'phone': '9876543210'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Registration Confirmed', response.data)
        self.assertIn(b'REG-', response.data)

        # Check in my registrations
        my_reg = self.client.get('/events/my-registrations')
        self.assertIn(b'REG-', my_reg.data)

    def test_11_paid_event_demo_payment(self):
        """Verify paid event demo payment flow."""
        rnd = random.randint(10000, 99999)
        test_email = f"student_paid{rnd}@college.edu.in"

        # Verify email first
        s_res = self.client.post('/api/send-verification-code', json={'email': test_email})
        self.assertEqual(s_res.status_code, 200)
        d_code = s_res.get_json()['dev_code']
        self.client.post('/api/verify-code', json={'email': test_email, 'code': d_code})

        self.client.post('/register', data={
            'name': 'Kiran Varma',
            'roll_number': f'22ECE{rnd}',
            'branch': 'ECE',
            'year': '2nd Year',
            'email': test_email,
            'phone': '9876501234',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)

        # Register for paid event (Event 2: Code Sprint Challenge, fee ₹100)
        reg_res = self.client.post('/events/2/register', data={
            'student_name': 'Kiran Varma',
            'roll_number': f'22ECE{rnd}',
            'branch': 'ECE',
            'year': '2nd Year',
            'email': test_email,
            'phone': '9876501234'
        }, follow_redirects=True)
        self.assertIn(b'DEMO PAYMENT GATEWAY', reg_res.data)
        self.assertIn(b'Demo Payment', reg_res.data)

        # Complete demo payment
        pay_res = self.client.post('/events/2/payment', data={
            'payment_method': 'UPI / QR Code',
            'transaction_ref': 'UPI-DEMO-TEST-99'
        }, follow_redirects=True)
        self.assertEqual(pay_res.status_code, 200)
        self.assertIn(b'Registration Confirmed', pay_res.data)

    def test_12_profile_update(self):
        """Verify viewing and editing student profile with roll number, branch, year."""
        self.client.post('/login', data={'identifier': 'rahul@stuhub.edu', 'password': 'student123'})
        response = self.client.post('/profile/edit', data={
            'name': 'Rahul Sharma',
            'roll_number': '22CSE045',
            'branch': 'Computer Science & Engineering',
            'year': '4th Year',
            'phone': '9876543210'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Rahul Sharma', response.data)
        self.assertIn(b'4th Year', response.data)

    def test_13_admin_complaint_status_update(self):
        """Verify admin can change complaint status (Pending -> In Progress -> Resolved)."""
        self.client.post('/login', data={'identifier': 'admin@stuhub.edu', 'password': 'admin123'})
        response = self.client.post('/admin/complaint/update/1', data={
            'status': 'In Progress'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'status changed to In Progress', response.data)

    def test_14_admin_events_management(self):
        """Verify admin can toggle event status, view registrations and attendee list."""
        self.client.post('/login', data={'identifier': 'admin@stuhub.edu', 'password': 'admin123'})
        
        # View event registrations roster
        roster_res = self.client.get('/admin/events/1/registrations')
        self.assertEqual(roster_res.status_code, 200)
        self.assertIn(b'Registered Students', roster_res.data)
        self.assertIn(b'Total Students Registered', roster_res.data)

        # Toggle event status
        toggle_res = self.client.post('/admin/events/toggle-status/1', follow_redirects=True)
        self.assertEqual(toggle_res.status_code, 200)

    def test_15_college_email_domain_rejection(self):
        """Verify registration rejects commercial/personal emails (Gmail, Yahoo, Outlook)."""
        personal_emails = ['fake@gmail.com', 'user@yahoo.com', 'test@outlook.com', 'student@hotmail.com']
        for bad_email in personal_emails:
            # Rejection on API
            api_res = self.client.post('/api/send-verification-code', json={'email': bad_email})
            self.assertEqual(api_res.status_code, 400)
            self.assertIn('official college email address', api_res.get_json()['message'])

            # Rejection on Form Submit
            reg_res = self.client.post('/register', data={
                'name': 'Test User',
                'roll_number': '22CSE999',
                'branch': 'CSE',
                'year': '1st Year',
                'email': bad_email,
                'password': 'password123',
                'confirm_password': 'password123'
            }, follow_redirects=True)
            self.assertIn(b'Please use your official college email address', reg_res.data)

    def test_16_college_email_verification_flow(self):
        """Verify 6-digit verification code generation, invalid code rejection, and verification."""
        test_email = f"verify_test_{int(time.time())}@college.ac.in"

        # 1. Send code
        res = self.client.post('/api/send-verification-code', json={'email': test_email})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        dev_code = data['dev_code']
        self.assertEqual(len(dev_code), 6)

        # 2. Test wrong code
        bad_ver = self.client.post('/api/verify-code', json={'email': test_email, 'code': '000000'})
        self.assertEqual(bad_ver.status_code, 400)
        self.assertIn('Invalid Verification Code', bad_ver.get_json()['message'])

        # 3. Test correct code
        good_ver = self.client.post('/api/verify-code', json={'email': test_email, 'code': dev_code})
        self.assertEqual(good_ver.status_code, 200)
        self.assertIn('Email Verified Successfully', good_ver.get_json()['message'])

    def test_17_unverified_student_cannot_login(self):
        """Verify that an unverified student account is blocked from login with warning."""
        unverified_email = f"unverified_{int(time.time())}@stuhub.edu"
        # Directly insert an unverified student
        with app.app_context():
            db = get_db()
            db.cursor().execute('''
                INSERT INTO users (name, email, password_hash, role, email_verified)
                VALUES ('Unverified Student', ?, ?, 'student', 0)
            ''', (unverified_email, generate_password_hash('password123')))
            db.commit()

        # Try logging in
        login_res = self.client.post('/login', data={
            'identifier': unverified_email,
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Please verify your college email before logging in', login_res.data)

    def test_18_dashboard_action_cards_layout(self):
        """Verify dashboard displays 4 action cards and JUST YOUR ACTIVITY."""
        self.client.post('/login', data={'identifier': 'rahul@stuhub.edu', 'password': 'student123'})
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'LOST &amp; FOUND ITEMS', res.data)
        self.assertIn(b'COMPLAINTS RAISE', res.data)
        self.assertIn(b'CAMPUS EVENTS', res.data)
        self.assertIn(b'ANNOUNCEMENTS', res.data)
        self.assertIn(b'JUST YOUR ACTIVITY', res.data)

    def test_19_admin_events_portal_unified(self):
        """Verify unified Admin Events Portal with Upcoming Events, Past Events, and Action Buttons."""
        # Admin login
        self.client.post('/login', data={'identifier': 'admin@stuhub.edu', 'password': 'admin123'})

        # 1. Admin Dashboard contains EVENTS PORTAL card and STUDENTS card (no separate Post/Manage cards)
        admin_res = self.client.get('/admin')
        self.assertEqual(admin_res.status_code, 200)
        self.assertIn(b'EVENTS PORTAL', admin_res.data)
        self.assertIn(b'ANNOUNCEMENTS', admin_res.data)
        self.assertIn(b'COMPLAINTS', admin_res.data)
        self.assertIn(b'STUDENTS', admin_res.data)
        self.assertNotIn(b'POST CAMPUS EVENTS</h3>', admin_res.data)
        self.assertNotIn(b'MANAGE EVENTS</h3>', admin_res.data)

        # 2. Open dedicated Events Portal
        portal_res = self.client.get('/admin/events')
        self.assertEqual(portal_res.status_code, 200)
        self.assertIn(b'EVENTS PORTAL', portal_res.data)
        self.assertIn(b'+ POST NEW EVENT', portal_res.data)
        self.assertIn(b'UPCOMING EVENTS', portal_res.data)
        self.assertIn(b'View Students', portal_res.data)
        self.assertIn(b'View Details', portal_res.data)
        self.assertIn(b'Available Seats', portal_res.data)

        # 3. Regular student cannot access Admin Events Portal
        self.client.get('/logout')
        self.client.post('/login', data={'identifier': 'rahul@stuhub.edu', 'password': 'student123'})
        forbidden_res = self.client.get('/admin/events')
        self.assertEqual(forbidden_res.status_code, 302)

    def test_20_admin_student_registrations_access(self):
        """Verify Admin can view full student details in event registrations and students are restricted."""
        # Admin login
        self.client.post('/login', data={'identifier': 'admin@stuhub.edu', 'password': 'admin123'})
        roster_res = self.client.get('/admin/events/1/registrations')
        self.assertEqual(roster_res.status_code, 200)
        self.assertIn(b'Registered Students', roster_res.data)
        self.assertIn(b'Roll Number', roster_res.data)
        self.assertIn(b'Branch', roster_res.data)
        self.assertIn(b'College Email', roster_res.data)
        self.assertIn(b'Phone Number', roster_res.data)
        self.assertIn(b'Payment Status', roster_res.data)
        self.assertIn(b'Reg Status', roster_res.data)

        # Regular student cannot access event registrations roster
        self.client.get('/logout')
        self.client.post('/login', data={'identifier': 'rahul@stuhub.edu', 'password': 'student123'})
        student_blocked = self.client.get('/admin/events/1/registrations')
        self.assertEqual(student_blocked.status_code, 302)

if __name__ == '__main__':
    unittest.main()
