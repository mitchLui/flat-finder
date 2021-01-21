# Accommodation Search Script

An automation script that searches Zoopla and Rightmove for my accommodation for the 2021-2022 academic year.

**THIS SCRIPT IS NOT COMPLETE**
WIP:
- [ ] 

---

## Requirements

This script requires python 3.7 or above.
### config.json

Simply configure the key-value pairs under `requirements` in `config.json`:

```json
{
    "requirements": {
            "location": "Bristol",
            "beds": "4",
            "bathrooms": "2"
        }
}
```

| Key         | Description             | Note                        |
| ----------- | ----------------------- | --------------------------- |
| `location`  | Search Location         | Postcodes are supported     |
| `beds`      | Number of beds          | N/A                         |
| `bathrooms` | Number of bathrooms     | N/A                         |


### Libraries

Install the libraries required:

```sh
pip install -r requirements.txt
```

---

## Usage

Simply run the python script:

```sh
python3 accom_bot.py
```

---