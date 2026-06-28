from django.core.management.base import BaseCommand
from django.utils.text import slugify
from accounts.models import MembershipLevel
from bookings.models import ServiceCategory, Service
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seeds initial service categories, services, and membership levels'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding Membership Levels...")
        
        membership_data = [
            {"name": "Silver", "min_deposit_amount": Decimal("10000.00"), "discount_percentage": Decimal("5.00"), "description": "Silver membership: 5% discount on all bookings"},
            {"name": "Gold", "min_deposit_amount": Decimal("50000.00"), "discount_percentage": Decimal("10.00"), "description": "Gold membership: 10% discount on all bookings"},
            {"name": "VIP", "min_deposit_amount": Decimal("100000.00"), "discount_percentage": Decimal("15.00"), "description": "VIP membership: 15% discount on all bookings"},
        ]

        for m_level in membership_data:
            obj, created = MembershipLevel.objects.update_or_create(
                name=m_level["name"],
                defaults={
                    "min_deposit_amount": m_level["min_deposit_amount"],
                    "discount_percentage": m_level["discount_percentage"],
                    "description": m_level["description"]
                }
            )
            status = "created" if created else "updated"
            self.stdout.write(f"  Membership Level '{obj.name}' {status}.")

        self.stdout.write("Seeding Service Categories & Services...")

        categories_and_services = {
            "Hair Cut & Dye": {
                "description": "Premium haircut, grooming, and dyeing services",
                "services": [
                    {"name": "Barbing cut and dye", "price": Decimal("5000.00"), "duration": 45, "description": "Professional barbing haircut combined with hair dyeing"},
                    {"name": "Barbing", "price": Decimal("3000.00"), "duration": 30, "description": "Standard clean barbing haircut and shave"},
                ]
            },
            "Hair Locking": {
                "description": "Expert locking, twisting, and dreadlocks installation",
                "services": [
                    {"name": "Relocking", "price": Decimal("20000.00"), "duration": 120, "description": "Retightening and dressing existing locks"},
                    {"name": "Dread", "price": Decimal("40000.00"), "duration": 180, "description": "Full initial locks or dreadlocks installation and styling"},
                ]
            },
            "Wig Services": {
                "description": "Professional wig installation, styling, and revitalization",
                "services": [
                    {"name": "Installation: Swiss lace", "price": Decimal("15000.00"), "duration": 90, "description": "Professional installation of Swiss lace wig"},
                    {"name": "Installation hd lace", "price": Decimal("25000.00"), "duration": 90, "description": "Seamless installation of high-definition lace wig"},
                    {"name": "Wig styling", "price": Decimal("15000.00"), "duration": 60, "description": "Wig cleaning, brushing, and hot-tool styling"},
                    {"name": "Revamping and styling", "price": Decimal("15000.00"), "duration": 120, "description": "Deep washing, conditioning, repair, and restyling of wig"},
                ]
            },
            "Pedicure": {
                "description": "Relaxing spa pedicure and foot grooming",
                "services": [
                    {"name": "Male Pedicure", "price": Decimal("15000.00"), "duration": 45, "description": "Specialized spa pedicure for men"},
                    {"name": "Female Pedicure", "price": Decimal("10000.00"), "duration": 45, "description": "Deluxe spa pedicure for women"},
                ]
            }
        }

        for cat_name, cat_info in categories_and_services.items():
            cat_slug = slugify(cat_name)
            category, created = ServiceCategory.objects.update_or_create(
                slug=cat_slug,
                defaults={
                    "name": cat_name,
                    "description": cat_info["description"]
                }
            )
            cat_status = "created" if created else "updated"
            self.stdout.write(f"  Category '{category.name}' {cat_status}.")

            for svc in cat_info["services"]:
                service, svc_created = Service.objects.update_or_create(
                    category=category,
                    name=svc["name"],
                    defaults={
                        "price": svc["price"],
                        "duration_minutes": svc["duration"],
                        "description": svc["description"]
                    }
                )
                svc_status = "created" if svc_created else "updated"
                self.stdout.write(f"    Service '{service.name}' {svc_status}.")

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
