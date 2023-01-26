from modules.database import operations as dbo

if __name__ == '__main__':
    if input("Are you sure you want to drop DB data?\nType 'Yes, I am sure' to confirm or anything else to exit:\n") == 'Yes, I am sure':
        dbo.drop_database()