---

# 🧪 Django Testing Guide

This document provides a comprehensive guide on how to run and manage tests for the **HR Rewards & Penalties** module (and other Django apps) within the project.

---

## 📘 Overview

Django provides a built-in testing framework based on Python’s `unittest`.
All test files follow the naming convention `test*.py` and are automatically discovered by Django’s test runner.

In this project, tests are organized as follows:

* **Unit Tests:** Located in `hr/rewards_penalties/tests.py`
* **Integration Tests:** Located in `hr/rewards_penalties/tests_integration.py`

These tests cover:

* Model validation
* Signal triggers
* Serializer logic
* API endpoint integration
* Authentication and permission checks
* Business rule enforcement

---

## 🚀 Running Tests

All commands should be executed from the **project root directory** (where `manage.py` is located).

### 1. Run All Tests

```bash
python manage.py test
```

This command:

* Automatically discovers and runs all test files.
* Uses Django’s built-in test runner.
* Creates a temporary test database (no effect on production data).

---

### 2. Run Tests for a Specific App

```bash
python manage.py test hr.rewards_penalties
```

Useful when you only want to test the `rewards_penalties` module.

---

### 3. Run a Specific Test File

**Run only the unit tests:**

```bash
python manage.py test hr.rewards_penalties.tests
```

**Run only the integration tests:**

```bash
python manage.py test hr.rewards_penalties.tests_integration
```

---

### 4. Run a Specific Test Class or Method

**Example: Run one class**

```bash
python manage.py test hr.rewards_penalties.tests.ModelsTestCase
```

**Example: Run one test method**

```bash
python manage.py test hr.rewards_penalties.tests.ModelsTestCase.test_validate_details_json
```

---

### 5. Running Tests in Docker

If Django is containerized (e.g., service name: `hr`), use:

```bash
docker exec -it hr python manage.py test
```

This executes all tests inside the running container.

---

### 6. Verbosity and Failure Control

**Show detailed output:**

```bash
python manage.py test -v 2
```

**Stop at the first failed test:**

```bash
python manage.py test --failfast
```

You can also combine both:

```bash
python manage.py test -v 2 --failfast
```

---

## 🧱 How the Test Environment Works

* Django automatically:

  * Creates a **temporary test database**.
  * Runs all migrations.
  * Destroys the test database after the test run.

* Any test data created (via factories, fixtures, or serializers) exists only during the test session.

* Environment variables (like `DEBUG`, `JWT_SECRET`, etc.) should be loaded from the `.env` file or defined within the CI/CD environment.

---

## 🧰 Using `pytest` (Optional)

You can run Django tests using `pytest` with the `pytest-django` plugin for improved output and flexibility.

**Installation:**

```bash
pip install pytest pytest-django
```

**Run tests:**

```bash
pytest -v --ds=your_project.settings
```

---

## 🧩 Continuous Integration (Optional)

For automated testing during deployments (CI/CD), you can integrate these tests with tools like:

* **GitHub Actions**
* **GitLab CI**
* **Jenkins**
* **AWS CodeBuild**

Each pipeline can execute:

```bash
python manage.py test
```

before deployment to ensure all modules pass validation.

---

## ✅ Best Practices

* Write tests alongside each new feature or bug fix.
* Use descriptive test names (e.g., `test_create_reward_with_valid_data`).
* Keep unit and integration tests separate for clarity.
* Mock external APIs where applicable.
* Ensure CI/CD runs tests before merging code into the main branch.

---

### 📄 Summary

| Task                                       | Command                                                                                                      |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| **Run all tests**                          | `python manage.py test`                                                                                      |
| **Run specific app tests**                 | `python manage.py test rewards_penalties`                                                                    |
| **Run unit tests only**                    | `python manage.py test rewards_penalties.tests`                                                              |
| **Run integration tests only**             | `python manage.py test rewards_penalties.tests_integration`                                                  |
| **Run specific test class**                | `python manage.py test rewards_penalties.tests.ModelsTestCase`                                               |
| **Run specific test method**               | `python manage.py test rewards_penalties.tests.ModelsTestCase.test_validate_details_json`                    |
| **Run all tests inside Docker**            | `docker exec -it hr python manage.py test`                                                                   |
| **Run specific app tests inside Docker**   | `docker exec -it hr python manage.py test rewards_penalties`                                                 |
| **Run specific test class inside Docker**  | `docker exec -it hr python manage.py test rewards_penalties.tests.ModelsTestCase`                            |
| **Run specific test method inside Docker** | `docker exec -it hr python manage.py test rewards_penalties.tests.ModelsTestCase.test_validate_details_json` |

---
