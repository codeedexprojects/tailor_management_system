# from tailors.models import AddCustomer
import csv
from decimal import Decimal, InvalidOperation
import logging
import random
from django.urls import reverse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from datetime import date
import string
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.db import IntegrityError
from django.db.models import Sum
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import get_template
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView
from rest_framework.generics import UpdateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from xhtml2pdf import pisa
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import ProtectedError
from reception.views import reception_indexpage
from .models import AddTailors, Cloth
from .models import Customer, Item, reception_login, admin_login, Add_order
from .serializers import TailorLoginSerializer, \
    CompletedOrderSerializer, ItemSerializer, InProgressToCompletedSerializer, InProgressOrderSerializer, \
    UpdateToInProgressSerializer, AddOrderSerializer
from dashboard import models


# API


class TailorLoginView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = TailorLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        print(f"Attempting to authenticate user: {username}")

        user = authenticate(request, username=username, password=password)

        try:
            user = AddTailors.objects.get(username=username, password=password)
        except AddTailors.DoesNotExist:
            user = None

        if user:
            print(f"Authentication successful for user: {username}")
            refresh = RefreshToken.for_user(user)
            token = str(refresh.access_token)

            response_data = {
                'message': 'Authentication successful',
                'status': True,
                'token': token,
                'user_id': user.id,
                'username': user.username,
            }

            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"Authentication failed for user: {username}")
            response_data = {
                'error': 'Invalid credentials',
                'status': False,
            }
            return Response(response_data, status=status.HTTP_401_UNAUTHORIZED)


class TailorAssignedWorksAPIView(ListAPIView):
    serializer_class = AddOrderSerializer

    def get_queryset(self):
        tailor_id = self.kwargs['tailor_id']
        return Add_order.objects.filter(tailor_id=tailor_id, status='assigned')


class AssignedToInProgressAPIView(UpdateAPIView):
    serializer_class = UpdateToInProgressSerializer
    lookup_field = 'id'

    def get_queryset(self):
        tailor_id = self.kwargs['tailor_id']
        order_id = self.kwargs['id']
        return Add_order.objects.filter(tailor_id=tailor_id, id=order_id, status='assigned')

    def perform_update(self, serializer):
        # Retrieve the Add_order instance
        tailor_id = self.kwargs['tailor_id']
        order_id = self.kwargs['id']
        add_order_instance = get_object_or_404(Add_order, tailor_id=tailor_id, id=order_id, status='assigned')

        # Update the status to "in_progress"
        add_order_instance.status = 'in_progress'
        add_order_instance.save()

        # Update other related data or perform additional actions if needed

        # Update the pending works count for the tailor
        tailor_instance = get_object_or_404(AddTailors, id=tailor_id)

        # Decrease the pending works count, but ensure it doesn't go below 0
        if tailor_instance.pending_works > 0:
            tailor_instance.pending_works -= 1
        else:
            # If the pending works count is already 0, do not decrease it further
            tailor_instance.pending_works = 0

        tailor_instance.save()

        # Serialize the updated instance and return the response
        serialized_data = UpdateToInProgressSerializer(add_order_instance).data
        return Response(serialized_data, status=status.HTTP_200_OK)


class InProgressWorksAPIView(ListAPIView):
    serializer_class = InProgressOrderSerializer

    def get_queryset(self):
        tailor_id = self.kwargs['tailor_id']
        return Add_order.objects.filter(tailor_id=tailor_id, status='in_progress')


class InProgressToCompletedAPIView(UpdateAPIView):
    serializer_class = InProgressToCompletedSerializer
    lookup_field = 'id'

    def get_queryset(self):
        tailor_id = self.kwargs['tailor_id']
        order_id = self.kwargs['id']
        return Add_order.objects.filter(tailor_id=tailor_id, id=order_id, status='in_progress')

    def perform_update(self, serializer):
        # Retrieve the Add_order instance
        tailor_id = self.kwargs['tailor_id']
        order_id = self.kwargs['id']
        add_order_instance = get_object_or_404(Add_order, tailor_id=tailor_id, id=order_id, status='in_progress')

        # Update the status to "completed"
        add_order_instance.status = 'completed'
        add_order_instance.save()

        # Update other related data or perform additional actions if needed

        # Update the pending and completed works count for the tailor
        tailor_instance = get_object_or_404(AddTailors, id=tailor_id)

        # Check for negative values and handle them
        if tailor_instance.pending_works > 0:
            tailor_instance.pending_works -= 1
        else:
            tailor_instance.pending_works = 0

        tailor_instance.completed_works += 1
        tailor_instance.save()

        # Serialize the updated instance and return the response
        serialized_data = InProgressToCompletedSerializer(add_order_instance).data
        return Response(serialized_data, status=status.HTTP_200_OK)


class CompletedOrderListAPIView(ListAPIView):
    serializer_class = CompletedOrderSerializer

    def get_queryset(self):
        tailor_id = self.kwargs['tailor_id']
        return Add_order.objects.filter(tailor_id=tailor_id, status='completed')


class ItemListAPIView(ListAPIView):
    serializer_class = ItemSerializer

    def get_queryset(self):
        order_id = self.kwargs['order_id']
        return Item.objects.filter(order_id=order_id)


def indexpage(request):
    return render(request, "dashboard.html")


def createcustomer(request):
    tailor = AddTailors.objects.all()
    cloths = Cloth.objects.all()
    tailor_works = []
    for tailor in tailor:
        assigned_works = Add_order.objects.filter(tailor=tailor, status='assigned').count()
        pending_works = Add_order.objects.filter(tailor=tailor,status='in_progress').count()
        tailor_works.append({'tailor': tailor, 'assigned_works': assigned_works, 'pending_works': pending_works})

    context = {'tailor_works': tailor_works,'cloths': cloths}
    return render(request, 'Create_customer.html', context)


def add_cloth(request):
    if request.method == "POST":
        cloth = request.POST.get('clothname')
        length = float(request.POST.get('length'))
        
        # Save the cloth details to the database
        Cloth.objects.create(name=cloth, length=length, stock_length=length)
        
        # Redirect to a success page or render a success message
        messages.success(request, "Cloth Added Successfully")
        return redirect(add_cloth)
    else:
        # If it's a GET request, render the form
        return render(request, 'Add_cloth_admin.html')


def addtailors(request):
    return render(request, "Add_tailor.html")


def save_tailor(request):
    if request.method == "POST":
        tn = request.POST.get('tname')
        un = request.POST.get('username')
        pwd = request.POST.get('password')
        mob = request.POST.get('mobile')

        # Check if a tailor with the given mobile number already exists
        if AddTailors.objects.filter(mobile_number=mob).exists():
            messages.error(request, "Mobile number already exists")
        else:
            try:
                obj = AddTailors(tailor=tn, username=un, password=pwd, mobile_number=mob)
                obj.save()
                messages.success(request, "Tailor Added Successfully")
            except IntegrityError:
                messages.error(request, "An error occurred while saving the tailor")

    return redirect('addtailors')


# def view_tailors(request):
#     return render(request, "View_Tailor.html")


def tailor_details(request):
    tailors = AddTailors.objects.all()

    for tailor in tailors:
        # Calculate assigned, pending, upcoming, and completed works
        tailor.assigned_works = Add_order.objects.filter(tailor=tailor, status='assigned').count()
        tailor.pending_works = Add_order.objects.filter(tailor=tailor, status='in_progress').count()
        tailor.upcoming_works = Add_order.objects.filter(tailor=tailor, delivery_date__gt=date.today()).count()
        tailor.completed_works = Add_order.objects.filter(tailor=tailor, status='completed').count()

    context = {'tailors': tailors}
    return render(request, 'View_Tailor.html', context)

def generate_pdf_cloth_details(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="cloth_details.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []

    data = [
        ['Cloth Name', 'Available Cloth Length (Meter)']
    ]

    cloths = Cloth.objects.all()
    for cloth in cloths:
        data.append([cloth.name, str(cloth.stock_length)])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(table)
    doc.build(elements)
    return response

def Cloth_details_admin(request):
    query = request.GET.get('q')
    if query:
        cloth = Cloth.objects.filter(name__icontains=query)
    else:
        cloth = Cloth.objects.all()
    return render(request, 'Cloth_details_admin.html', {'cloth': cloth})

def add_stock(request, cloth_id):
    clothdetails=Cloth.objects.get(id=cloth_id)
    if request.method == 'POST':
        cloth = get_object_or_404(Cloth, pk=cloth_id)
        added_length = Decimal(request.POST.get('added_length'))  # Convert to Decimal
        cloth.stock_length += added_length
        cloth.save()
        return redirect('Cloth_details_admin')
    return render(request, 'add_stock.html', {'cloth_id': cloth_id,'clothdetails':clothdetails})

def update_stock(request, cloth_id):
    cloth_details = get_object_or_404(Cloth, id=cloth_id)
    if request.method == 'POST':
        new_length = request.POST.get('new_length') 
        clothname = request.POST.get('clothname') 
        cloth_details.stock_length = new_length
        cloth_details.name=clothname
        cloth_details.save()
        return redirect('Cloth_details_admin')  # Ensure this URL name matches your URL configuration
    return render(request, 'update_stock.html', {'cloth_id': cloth_id, 'cloth_details': cloth_details})


def additems(request, dataid):
    order = Add_order.objects.get(id=dataid)
    return render(request, "Add_items_admin.html", {"customers": order})


def additem(request, dataid):
    order = Add_order.objects.get(id=dataid)
    return render(request, "Add_Items.html", {'order': order})


def save_items(request):
    if request.method == 'POST':
        order_id = request.POST.get('orderid')
        customer = request.POST.get('customerid')
        item_names = request.POST.getlist('itemName[]')
        quantities = request.POST.getlist('quantity[]')
        prices = request.POST.getlist('price[]')

        order_instance = Add_order.objects.get(id=order_id)
        customer_instance = Customer.objects.get(id=customer)

        for i in range(len(item_names)):
            if i < len(quantities) and i < len(prices):
                item = Item(
                    order_id=order_instance,
                    customer=customer_instance,
                    item_name=item_names[i],
                    item_quantity=int(quantities[i]),
                    item_price=float(prices[i])
                )
                item.save()
            else:
                print(f"Skipping item at index {i} due to incomplete data.")

        return redirect('customer_details')


def customer_details(request):
    cus = Customer.objects.all().order_by('-id')

    # Pagination
    paginator = Paginator(cus, 300)  # Show 300 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "Customer_details.html",{'page_obj': page_obj})

def order_details(request):
    cus = Add_order.objects.all().order_by('-id')

    if request.method == "POST":
        from_date_str = request.POST.get('textfield')
        to_date_str = request.POST.get('textfield2')
        export = request.POST.get('export')

        if from_date_str and to_date_str:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            cus = Add_order.objects.filter(delivery_date__range=[from_date, to_date]).order_by('-id')

        if export:  # If export button was clicked, generate the CSV
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="order_details_{from_date_str}_to_{to_date_str}.csv"'

            writer = csv.writer(response)
            writer.writerow(['Order ID', 'Customer ID', 'Name', 'Contact Number', 'Cloth Name', 'Cloth Length', 'Model Details', 'Length', 'Shoulder', 'Sleeve Sada', 'Sleeve Cuff', 'Center Sleeve', 'Sleeve Bottom', 'Loose', 'Seat', 'Regal', 'Collar Type', 'Collar Measurement', 'Cuff Type', 'Cuff Measurements', 'Pocket Type', 'Pocket Measure', 'Button Type', 'Bottom Measure', 'Bill Number', 'Order Date', 'Delivery Date', 'Description', 'Total Price', 'Advance Payment', 'Balance Payment', 'Tailor'])

            for order in cus:
                writer.writerow([
                    order.id, order.customer_id.id, order.customer_id.name, order.customer_id.mobile, 
                    order.clothdetails.name if order.clothdetails else order.cloth_name, 
                    order.ordered_length, order.model_details, order.length, order.shoulder, 
                    order.sleeve_sada, order.sleeve_cuff, order.center_sleeve, order.sleeve_bottom, 
                    order.loose, order.seat, order.regal, order.collar_type, 
                    order.collar_measurements, order.cuff_type, order.cuff_measurements, 
                    order.pocket_type, order.pocket, order.button_type, order.bottom1, 
                    order.bill_number, order.order_date, order.delivery_date, order.description, 
                    order.total_payment, order.advance_payment, order.balance_payment, order.tailor
                ])

            return response

    # Pagination
    paginator = Paginator(cus, 300)  # Show 300 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "Order_Details.html", {'page_obj': page_obj})

def deliver_order(request, order_id):
    if request.method == 'POST':
        order = Add_order.objects.get(pk=order_id)
        order.pending_or_delivered = 'delivered'
        order.save()
        return redirect('order_details')


def upcoming_deliveries(request):
    cus = Customer.objects.filter(delivery_date__gte=date.today()).order_by('delivery_date')

    return render(request, 'dashboard.html', {'cus': cus})


def check_tailor_works(request):
    if request.method == 'GET':
        tailor_id = request.GET.get('tailor_id')
        delivery_date = request.GET.get('delivery_date')

        try:
            # Assuming you have a Customer model with a tailor field
            works = Add_order.objects.filter(tailor__id=tailor_id, delivery_date=delivery_date)

            # You may need to serialize the works data based on your requirements
            serialized_works = [{'name': work.name, 'other_field': work.other_field} for work in works]

            return JsonResponse({'works': serialized_works})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


def fetch_tailor_options(request):
    if request.method == 'GET' and 'delivery_date' in request.GET:
        delivery_date = request.GET.get('delivery_date')

        try:
            tailors = AddTailors.objects.all()
            tailor_options = []

            for tailor in tailors:
                try:
                    # Access the related set of Customer objects using customer_set
                    works_on_date = tailor.add_order_set.filter(delivery_date=delivery_date)

                    # Count assigned and pending works separately
                    assigned_works = works_on_date.filter(status='assigned').count()
                    pending_works = works_on_date.filter(status='pending').count()

                    tailor_options.append({
                        'id': tailor.id,
                        'name': tailor.tailor,
                        'assigned_works': assigned_works,
                        'pending_works': pending_works,
                    })
                except Exception as e:
                    print(f"Error processing tailor {tailor.id}: {str(e)}")

            return JsonResponse({'tailor_options': tailor_options})

        except Exception as e:
            # Print the error details to the console
            import traceback
            print(traceback.format_exc())

            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request'}, status=400)


def savecustomer(request):
    context = {}

    if request.method == "POST":
        nm = request.POST.get('name')
        mn = request.POST.get('mobile')
        ln = request.POST.get('length')
        sd = request.POST.get('shoulder')
        sl = request.POST.get('sleeve_sada')
        sll = request.POST.get('sleeve_cuff')        
        center_sleeve = request.POST.get('center_sleeve')        
        rg = request.POST.get('regal')
        lo = request.POST.get('loose')
        po = request.POST.get('pocket')
        b1 = request.POST.get('bottom1')
        b2 = request.POST.get('seat')
        od = request.POST.get('order_date')
        dd = request.POST.get('delivery_date')
        bt = request.POST.get('button_type')
        ds = request.POST.get('other')
        tailor_id = request.POST.get('tailor')
        sb = request.POST.get('sleeve_bottom')
        tp = request.POST.get('total')
        ap = request.POST.get('advance')
        bp = request.POST.get('balance')
        collar_type = request.POST.get('collar-type')
        cuff_type = request.POST.get('cuff-type')
        cuff_measurment = request.POST.get('cuff-measurements')
        collar_measurment = request.POST.get('collar-measurements')
        model_details = request.POST.get('model_details')
        cloth_id = request.POST.get('cloth_id')
        pocket_type = request.POST.get('pocket-type')
        ordered_length_str = request.POST.get('ordered_length', '').strip()
        try:
            if ordered_length_str:
                ordered_length = Decimal(ordered_length_str)
            elif cloth_id:
                ordered_length = Decimal(3.5)
            else:
                ordered_length = None
        except InvalidOperation:
            messages.error(request, "Invalid value for ordered length.")
            return redirect('createcustomer')
        cloth_name = None
        

        if collar_type == 'collar1':
            collar_image_url = 'images/collarcuff/collor 1.png'
        elif collar_type == 'collar2':
            collar_image_url = 'images/collarcuff/collor 2.png'
        elif collar_type == 'collar3':
            collar_image_url = 'images/collarcuff/collor 3.png'
        elif collar_type == 'collar4':
            collar_image_url = 'images/collarcuff/collor 4.png'
        else:
            collar_image_url = None 

        if pocket_type == 'pocket1':
            pocket_image_url = 'images/collarcuff/pocket1.png'
        elif pocket_type == 'pocket2':
            pocket_image_url = 'images/collarcuff/pocket2.png'
        elif pocket_type == 'pocket3':
            pocket_image_url = 'images/collarcuff/pocket3.png'
        else:
            pocket_image_url = None 

        if cuff_type == 'cuff1':
            cuff_image_url = 'images/collarcuff/cuff 1.png'
        elif cuff_type == 'cuff2':
            cuff_image_url = 'images/collarcuff/cuff 2.png'
        elif cuff_type == 'cuff3':
            cuff_image_url = 'images/collarcuff/cuff 3.png'
        elif cuff_type == 'cuff4':
            cuff_image_url = 'images/collarcuff/cuff 4.png'
        elif cuff_type == 'cuff5':
            cuff_image_url = 'images/collarcuff/cuff 5.png'
        else:
            cuff_image_url = None 

        tailor_instance = AddTailors.objects.get(id=tailor_id)

        works_on_delivery_date = Add_order.objects.filter(tailor=tailor_instance, delivery_date=dd).count()


        tailor_instance.assigned_works += 1
        tailor_instance.save()

        cloth = None
        if cloth_id:
            try:
                cloth = Cloth.objects.get(pk=cloth_id)
                cloth_name=cloth.name
                if cloth.stock_length >= ordered_length:
                    cloth.stock_length -= ordered_length
                    cloth.save()
                else:
                    messages.error(request, "Not enough cloth stock available.")
                    return redirect('createcustomer')
            except Cloth.DoesNotExist:
                messages.error(request, "Cloth does not exist.")
                return redirect('createcustomer')
        else:
            ordered_length = None

        try:
            # Generate a unique bill_number sequentially
            last_bill_number = Add_order.objects.order_by('-bill_number').first()

            if last_bill_number:
                last_bill_chars = last_bill_number.bill_number[:1]  # Extract the first character
                last_bill_digits = int(last_bill_number.bill_number[1:])  # Extract the digits

                if last_bill_chars == 'Z' and last_bill_digits == 999:
                    raise ValueError("Cannot generate more bills")
                elif last_bill_digits == 999:
                    next_chars = chr(ord(last_bill_chars) + 1)  # Increment the character
                    if next_chars > 'Z':  # Check if the next character exceeds 'Z'
                        raise ValueError("Cannot generate more bills")
                    bill_number = f"{next_chars}001"  # Reset digits to "001"
                else:
                    bill_number = f"{last_bill_chars}{last_bill_digits + 1:03d}"  # Increment digits
            else:
                bill_number = "A001"


            obj = Customer(name=nm, mobile=mn, length=ln, shoulder=sd, loose=lo, regal=rg, collar_measurements=collar_measurment,
                           cuff_type_image_url=cuff_image_url, sleeve_sada=sl, sleeve_cuff=sll, pocket=po, bottom1=b1, seat=b2,
                           order_date=od, delivery_date=dd, tailor=tailor_instance, button_type=bt,collar_type=collar_type,
                           cuff_type=cuff_type,collar_type_image_url=collar_image_url, description=ds, bill_number=bill_number,
                           cuff_measurements=cuff_measurment,sleeve_bottom=sb,center_sleeve=center_sleeve,model_details=model_details,
                           clothdetails=cloth,pocket_image_url=pocket_image_url,pocket_type=pocket_type,ordered_length=ordered_length,
                           cloth_name=cloth_name)
            obj.save()

            add_order_obj = Add_order(customer_id=obj, length=ln, shoulder=sd, loose=lo,regal=rg,
                                      cuff_measurements=cuff_measurment,collar_type_image_url=collar_image_url,
                                      cuff_type_image_url=cuff_image_url, collar_measurements=collar_measurment,
                                      collar_type=collar_type,cuff_type=cuff_type,center_sleeve=center_sleeve,
                                      sleeve_sada=sl, sleeve_cuff=sll, pocket=po, bottom1=b1, seat=b2,
                                      order_date=od, delivery_date=dd, tailor=tailor_instance,cloth_name=cloth_name,
                                      button_type=bt,total_payment=tp,advance_payment=ap,balance_payment=bp,
                                      description=ds, bill_number=bill_number,sleeve_bottom=sb,model_details=model_details,
                                      clothdetails=cloth,pocket_image_url=pocket_image_url,pocket_type=pocket_type,ordered_length=ordered_length)
            add_order_obj.save()

            messages.success(request, "Successfully added customer")
            return redirect(createcustomer)
        except IntegrityError as e:
            # Handle IntegrityError
            return JsonResponse({'error': f"IntegrityError: {str(e)}"}, status=500)
        except Exception as e:
            # Handle other exceptions
            return JsonResponse({'error': f"Error saving customer: {str(e)}"}, status=500)


@api_view(['POST'])
def accept_work(request, tailor_id):
    tailor = get_object_or_404(AddTailors, id=tailor_id)

    # Update the pending works count
    tailor.pending_works += 1
    tailor.save()

    return Response({'status': 'Pending works updated successfully'}, status=status.HTTP_200_OK)


@api_view(['POST'])
def complete_work(request, tailor_id):
    tailor = get_object_or_404(AddTailors, id=tailor_id)

    # Update the pending and completed works counts
    if tailor.pending_works > 0:
        tailor.pending_works -= 1
        tailor.completed_works += 1
        tailor.save()
        return Response({'status': 'Work completed successfully'}, status=status.HTTP_200_OK)
    else:
        return Response({'status': 'No pending works to complete'}, status=status.HTTP_400_BAD_REQUEST)


def customerdlt(request, dlt):
    delt = Customer.objects.filter(id=dlt)
    delt.delete()
    return redirect(customer_details)


def orderdlt(request, dlt):
    delt = Add_order.objects.filter(id=dlt)
    id = Add_order.objects.get(id=dlt)
    id_dlt = id.tailor.id
    id_cloth=id.clothdetails
    delt.delete()
    tailor_instance = AddTailors.objects.get(id=id_dlt)
    tailor_instance.assigned_works -= 1
    tailor_instance.save()
    if id.ordered_length:
        id_cloth.stock_length += id.ordered_length
        id_cloth.save()
    return redirect(order_details)


def cloth_delete(request, cloth_id):
    cloth = get_object_or_404(Cloth, id=cloth_id)
    cloth.delete()
    messages.success(request, "Cloth deleted successfully.")
    return redirect(reverse('Cloth_details_admin'))

from django.shortcuts import redirect

def login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')  # Redirect to login page if user is not authenticated
        return view_func(request, *args, **kwargs)
    return wrapper

@login_required
def dashboard(request):
    total_customers = Customer.objects.count()
    total_order = Add_order.objects.count()  # Assuming you have an Order model

    total_completed_works = AddTailors.objects.aggregate(Sum('completed_works'))['completed_works__sum']

    cus = Add_order.objects.filter(delivery_date__gte=date.today()).order_by('delivery_date')

    context = {'total_customers': total_customers, 'total_orders': total_order,
               'cus': cus,
               'total_completed_works': total_completed_works}

    return render(request, 'dashboard.html', context)





def customer_bill(request, customer_id):
    order = get_object_or_404(Add_order, id=customer_id)
    item = Item.objects.filter(order_id=customer_id)

    return render(request, 'Print_measurements.html', {'order': order, 'item': item})


def update_print_status(request, customer_id):
    if request.method == 'POST':
        order = get_object_or_404(Add_order, id=customer_id)
        if not order.is_printed:
            order.is_printed = True
            order.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'failed'}, status=400)

def print_measurement(request, customer_id):
    customer = Add_order.objects.get(id=customer_id)

    context = {'customer': customer}

    template_path = 'Print_measurements.html'
    template = get_template(template_path)
    html = template.render(context)

    # Debugging: Print HTML to console
    print(html)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=measurement_{customer_id}.pdf'

    # Create PDF from HTML content
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('Error generating PDF', content_type='text/plain')

    return response


# def tailor_details(request):
#     # tailors = AddTailors.objects.all()
#
#     context = {'tailors': tailors}
#     return render(request, 'View_Tailor.html', context)


def all_customers(request):
    customers = Customer.objects.all()
    return render(request, 'customer_list.html', {'customers': customers})


def edit_tailor(request, dataid):
    tail = AddTailors.objects.get(id=dataid)
    return render(request, "edit_tailor.html", {"tail": tail})


def updatetailor(request, dataid):
    if request.method == "POST":
        tn = request.POST.get('tname')
        un = request.POST.get('username')
        pwd = request.POST.get('password')
        mob = request.POST.get('mobile')
        AddTailors.objects.filter(id=dataid).update(tailor=tn, username=un, password=pwd, mobile_number=mob)
        messages.success(request, "Tailor Details Updated Successfully...!")
    return redirect(tailor_details)


def delete_tailor(request, dataid):
    tailor = get_object_or_404(AddTailors, pk=dataid)

    # Add your logic for deleting tailor here
    tailor.delete()

    return redirect('view_tailors')


def edit_customer(request, dataid):
    ed = Customer.objects.all()
    cus = Customer.objects.get(id=dataid)
    cloths=Cloth.objects.all()
    return render(request, "edit_customer.html", {"cus": cus, "ed": ed,'cloths':cloths})


def update_customer(request, dataid):
    if request.method == "POST":
        nm = request.POST.get('name')
        mn = request.POST.get('mobile')
        ln = request.POST.get('length')
        sd = request.POST.get('shoulder')
        sl = request.POST.get('sleeve_sada')
        sll = request.POST.get('sleeve_cuff')
        rg = request.POST.get('regal')
        lo = request.POST.get('loose')
        po = request.POST.get('pocket')
        b1 = request.POST.get('bottom1')
        b2 = request.POST.get('seat')
        od = request.POST.get('order_date')
        dd = request.POST.get('delivery_date')
        bt = request.POST.get('button_type')
        tailor_id = request.POST.get('tailor')
        other = request.POST.get('other')
        sb = request.POST.get('sleeve_bottom')
        center_sleeve = request.POST.get('center_sleeve')
        collar_type = request.POST.get('collar-type')
        cuff_type = request.POST.get('cuff-type')
        cuff_measurment = request.POST.get('cuff-measurements')
        collar_measurment = request.POST.get('collar-measurements')
        model_details = request.POST.get('model_details')
        cloth_id = request.POST.get('cloth_id') or request.POST.get('existing_cloth_id')
        pocket_type = request.POST.get('pocket-type')
        ordered_length_str = request.POST.get('ordered_length', '').strip()
        try:
            if ordered_length_str:
                ordered_length = Decimal(ordered_length_str)
            elif cloth_id:
                ordered_length = Decimal(3.5)
            else:
                ordered_length = None
        except InvalidOperation:
            messages.error(request, "Invalid value for ordered length.")
            return redirect('customer_details')
        cloth_name=None


        if collar_type == 'collar1':
            collar_image_url = 'images/collarcuff/collor 1.png'
        elif collar_type == 'collar2':
            collar_image_url = 'images/collarcuff/collor 2.png'
        elif collar_type == 'collar3':
            collar_image_url = 'images/collarcuff/collor 3.png'
        elif collar_type == 'collar4':
            collar_image_url = 'images/collarcuff/collor 4.png'
        else:
            collar_image_url = None 

        if pocket_type == 'pocket1':
            pocket_image_url = 'images/collarcuff/pocket1.png'
        elif pocket_type == 'pocket2':
            pocket_image_url = 'images/collarcuff/pocket2.png'
        elif pocket_type == 'pocket3':
            pocket_image_url = 'images/collarcuff/pocket3.png'
        else:
            pocket_image_url = None 

        if cuff_type == 'cuff1':
            cuff_image_url = 'images/collarcuff/cuff 1.png'
        elif cuff_type == 'cuff2':
            cuff_image_url = 'images/collarcuff/cuff 2.png'
        elif cuff_type == 'cuff3':
            cuff_image_url = 'images/collarcuff/cuff 3.png'
        elif cuff_type == 'cuff4':
            cuff_image_url = 'images/collarcuff/cuff 4.png'
        elif cuff_type == 'cuff5':
            cuff_image_url = 'images/collarcuff/cuff 5.png'
        else:
            cuff_image_url = None 


        # Get the existing customer
        customer = Customer.objects.get(id=dataid)
        # previous_ordered_length = Decimal(str(customer.ordered_length))
        # ordered_length_decimal = Decimal(str(ordered_length))
        # length_difference = ordered_length_decimal - previous_ordered_length

        # # Handle cloth stock updates
        # if str(customer.clothdetails.id) == cloth_id:
        #     # Same cloth
        #     if ordered_length_decimal < previous_ordered_length:
        #         # New length is less, add the difference back to the stock
        #         customer.clothdetails.stock_length += abs(length_difference)
        #     else:
        #         # New length is more, subtract the difference from the stock
        #         if customer.clothdetails.stock_length >= length_difference:
        #             customer.clothdetails.stock_length -= length_difference
        #         else:
        #             messages.error(request, "Not enough cloth stock available.")
        #             return redirect('customer_details')
        # else:
        #     # Different cloth
        #     previous_cloth = get_object_or_404(Cloth, pk=customer.clothdetails.id)
        #     previous_cloth.stock_length += previous_ordered_length
        #     previous_cloth.save()

        #     new_cloth = get_object_or_404(Cloth, pk=cloth_id)
        #     if new_cloth.stock_length >= ordered_length_decimal:
        #         new_cloth.stock_length -= ordered_length_decimal
        #         customer.clothdetails = new_cloth
        #     else:
        #         messages.error(request, "Not enough cloth stock available.")
        #         return redirect('customer_details')

        # customer.clothdetails.save()
        cloth=None
        cloth = Cloth.objects.get(pk=cloth_id)
        cloth_name=cloth.name
        # Update the customer instance
        Customer.objects.filter(id=dataid).update(
            name=nm, mobile=mn, length=ln, shoulder=sd, loose=lo,
            regal=rg, sleeve_sada=sl,
            sleeve_cuff=sll, pocket=po, bottom1=b1, seat=b2, button_type=bt,
            description=other,sleeve_bottom=sb,model_details=model_details,cloth_name=cloth_name,
            cuff_measurements=cuff_measurment,collar_type_image_url=collar_image_url,
            cuff_type_image_url=cuff_image_url, collar_measurements=collar_measurment,
            collar_type=collar_type,cuff_type=cuff_type,center_sleeve=center_sleeve,ordered_length=ordered_length,
            clothdetails=cloth_id,pocket_image_url=pocket_image_url,pocket_type=pocket_type
        )
        messages.success(request, "Customer Details Updated Successfully...!")

    return redirect('customer_details')


def search_mobile(request):
    results = {'Customer': []}
    query = ""

    if 'q' in request.GET:
        query = request.GET['q']

        results['customer'] = Add_order.objects.filter(customer_id__mobile__icontains=query).exclude(customer_id__mobile__isnull=True).exclude(customer_id__mobile__exact='').order_by('-id')

    return render(request, 'search.html', {'results': results, 'query': query})


def single_customer(request, customer_id):
    single = Customer.objects.filter(id=customer_id)
    view_add_order = Add_order.objects.filter(customer_id=customer_id)
    itms = Item.objects.filter(customer_id=customer_id)
    return render(request, "single_customer.html", {'single': single, 'itms': itms, 'view': view_add_order})


def add_order(request, dataid):
    add = Customer.objects.get(id=dataid)
    cloths=Cloth.objects.all()
    return render(request, "Add_order.html", {'add': add,'cloths':cloths})


def edit_order(request, dataid):
    add = Add_order.objects.get(id=dataid)
    cloths=Cloth.objects.all()
    return render(request, "edit_order.html", {"add": add,'cloths':cloths})


def update_add_order(request, dataid):
    if request.method == "POST":
        # Your existing form processing logic
        id = request.POST.get('id')
        nm = request.POST.get('name')
        mn = request.POST.get('mobile')
        ln = request.POST.get('length')
        sd = request.POST.get('shoulder')
        sl = request.POST.get('sleeve_sada')
        sll = request.POST.get('sleeve_cuff')
        rg = request.POST.get('regal')
        lo = request.POST.get('loose')
        po = request.POST.get('pocket')
        b1 = request.POST.get('bottom1')
        b2 = request.POST.get('seat')
        od = request.POST.get('order_date')
        dd = request.POST.get('delivery_date')
        bt = request.POST.get('button_type')
        tailor_id = request.POST.get('tailor')
        other = request.POST.get('other')
        sb = request.POST.get('sleeve_bottom')
        tp = request.POST.get('total')
        ap = request.POST.get('advance')
        bp = request.POST.get('balance')
        center_sleeve = request.POST.get('center_sleeve')
        collar_type = request.POST.get('collar-type')
        cuff_type = request.POST.get('cuff-type')
        cuff_measurment = request.POST.get('cuff-measurements')
        collar_measurment = request.POST.get('collar-measurements')
        model_details = request.POST.get('model_details')
        cloth_id = request.POST.get('cloth_id') or request.POST.get('existing_cloth_id')
        pocket_type = request.POST.get('pocket-type')
        ordered_length_str = request.POST.get('ordered_length', '').strip()
        try:
            if ordered_length_str:
                ordered_length = Decimal(ordered_length_str)
            elif cloth_id:
                ordered_length = Decimal(3.5)
            else:
                ordered_length = None
        except InvalidOperation:
            messages.error(request, "Invalid value for ordered length.")
            return redirect('order_details')
        cloth_name=None


        if collar_type == 'collar1':
            collar_image_url = 'images/collarcuff/collor 1.png'
        elif collar_type == 'collar2':
            collar_image_url = 'images/collarcuff/collor 2.png'
        elif collar_type == 'collar3':
            collar_image_url = 'images/collarcuff/collor 3.png'
        elif collar_type == 'collar4':
            collar_image_url = 'images/collarcuff/collor 4.png'
        else:
            collar_image_url = None 

        if pocket_type == 'pocket1':
            pocket_image_url = 'images/collarcuff/pocket1.png'
        elif pocket_type == 'pocket2':
            pocket_image_url = 'images/collarcuff/pocket2.png'
        elif pocket_type == 'pocket3':
            pocket_image_url = 'images/collarcuff/pocket3.png'
        else:
            pocket_image_url = None 

        if cuff_type == 'cuff1':
            cuff_image_url = 'images/collarcuff/cuff 1.png'
        elif cuff_type == 'cuff2':
            cuff_image_url = 'images/collarcuff/cuff 2.png'
        elif cuff_type == 'cuff3':
            cuff_image_url = 'images/collarcuff/cuff 3.png'
        elif cuff_type == 'cuff4':
            cuff_image_url = 'images/collarcuff/cuff 4.png'
        elif cuff_type == 'cuff5':
            cuff_image_url = 'images/collarcuff/cuff 5.png'
        else:
            cuff_image_url = None
        

        # Get the existing customer
        customer = Add_order.objects.get(id=dataid)

        # Get the old tailor before updating
        old_tailor = customer.tailor

        tailor_instance = AddTailors.objects.get(id=tailor_id)

        works_on_delivery_date = Add_order.objects.filter(tailor=tailor_instance, delivery_date=dd).count()

        # Get or create the new tailor instance
        new_tailor = AddTailors.objects.get(id=tailor_id)

        order = get_object_or_404(Add_order, id=dataid)
        previous_ordered_length =  order.ordered_length or Decimal('0')
        ordered_length_decimal = ordered_length or Decimal('0')

        if cloth_id:
            # Handling case when cloth_id is provided and valid
            if not order.clothdetails or str(order.clothdetails.id) != cloth_id or previous_ordered_length != ordered_length_decimal:
                length_difference = ordered_length_decimal - previous_ordered_length
                if order.clothdetails and str(order.clothdetails.id) == cloth_id:
                    if ordered_length_decimal < previous_ordered_length:
                        order.clothdetails.stock_length += abs(length_difference)
                    else:
                        if order.clothdetails.stock_length >= length_difference:
                            order.clothdetails.stock_length -= length_difference
                        else:
                            messages.error(request, "Not enough cloth stock available.")
                            return redirect('order_details')
                else:
                    if order.clothdetails:
                        previous_cloth = get_object_or_404(Cloth, pk=order.clothdetails.id)
                        previous_cloth.stock_length += previous_ordered_length
                        previous_cloth.save()

                    new_cloth = get_object_or_404(Cloth, pk=cloth_id)
                    if new_cloth.stock_length >= ordered_length_decimal:
                        new_cloth.stock_length -= ordered_length_decimal
                        order.clothdetails = new_cloth
                    else:
                        messages.error(request, "Not enough cloth stock available.")
                        return redirect('order_details')

                if order.clothdetails:
                    order.clothdetails.save()
        else:
            # **Handling case when cloth_id is empty (remove cloth selection)**
            if order.clothdetails:
                previous_cloth = get_object_or_404(Cloth, pk=order.clothdetails.id)
                previous_cloth.stock_length += previous_ordered_length
                previous_cloth.save()
            order.clothdetails = None
            ordered_length = None
        cloth_name=order.clothdetails.name

        if order.customer_id:
            customer = order.customer_id
            customer.name = nm
            customer.mobile = mn
            customer.save()
            
        # Update assigned_works for the old tailor and new tailor
        if old_tailor != new_tailor:
            old_tailor.assigned_works -= 1
            old_tailor.save()
            new_tailor.assigned_works += 1
            new_tailor.save()
        Add_order.objects.filter(id=dataid).update(length=ln, shoulder=sd, loose=lo, 
                                                   regal=rg, sleeve_sada=sl,cloth_name=cloth_name,
                                                   sleeve_cuff=sll, pocket=po, bottom1=b1, seat=b2,
                                                   total_payment=tp,advance_payment=ap,balance_payment=bp,
                                                   order_date=od, delivery_date=dd, tailor=new_tailor,
                                                   button_type=bt,model_details=model_details,
                                                    cuff_measurements=cuff_measurment,collar_type_image_url=collar_image_url,
                                                    cuff_type_image_url=cuff_image_url, collar_measurements=collar_measurment,
                                                    collar_type=collar_type,cuff_type=cuff_type,center_sleeve=center_sleeve,
                                                    description=other,sleeve_bottom=sb,pocket_type=pocket_type,ordered_length=ordered_length,
                                                    clothdetails=order.clothdetails,pocket_image_url=pocket_image_url)

    messages.success(request, "Customer Details Updated Successfully...!")
    return redirect(order_details)


def save_add_order(request):
    if request.method == "POST":
        # Your existing form processing logic
        id = request.POST.get('id')
        nm = request.POST.get('name')
        mn = request.POST.get('mobile')
        ln = request.POST.get('length')
        sd = request.POST.get('shoulder')
        sl = request.POST.get('sleeve_sada')
        sll = request.POST.get('sleeve_cuff')
        center_sleeve = request.POST.get('center_sleeve')
        rg = request.POST.get('regal')
        lo = request.POST.get('loose')
        po = request.POST.get('pocket')
        b1 = request.POST.get('bottom1')
        b2 = request.POST.get('seat')
        od = request.POST.get('order_date')
        dd = request.POST.get('delivery_date')
        bt = request.POST.get('button_type')
        tailor_id = request.POST.get('tailor')
        other = request.POST.get('other')
        sb = request.POST.get('sleeve_bottom')
        tp = request.POST.get('total')
        ap = request.POST.get('advance')
        bp = request.POST.get('balance')
        collar_type = request.POST.get('collar-type')
        cuff_type = request.POST.get('cuff-type')
        cuff_measurment = request.POST.get('cuff-measurements')
        collar_measurment = request.POST.get('collar-measurements')
        model_details = request.POST.get('model_details')
        cloth_id = request.POST.get('cloth_id')
        existing_cloth_id = request.POST.get('existing_cloth_id')
        pocket_type = request.POST.get('pocket-type')
        ordered_length_str = request.POST.get('ordered_length', '').strip()
        cloth_name = None
        

        if collar_type == 'collar1':
            collar_image_url = 'images/collarcuff/collor 1.png'
        elif collar_type == 'collar2':
            collar_image_url = 'images/collarcuff/collor 2.png'
        elif collar_type == 'collar3':
            collar_image_url = 'images/collarcuff/collor 3.png'
        elif collar_type == 'collar4':
            collar_image_url = 'images/collarcuff/collor 4.png'
        else:
            collar_image_url = None 

        if pocket_type == 'pocket1':
            pocket_image_url = 'images/collarcuff/pocket1.png'
        elif pocket_type == 'pocket2':
            pocket_image_url = 'images/collarcuff/pocket2.png'
        elif pocket_type == 'pocket3':
            pocket_image_url = 'images/collarcuff/pocket3.png'
        else:
            pocket_image_url = None

        if cuff_type == 'cuff1':
            cuff_image_url = 'images/collarcuff/cuff 1.png'
        elif cuff_type == 'cuff2':
            cuff_image_url = 'images/collarcuff/cuff 2.png'
        elif cuff_type == 'cuff3':
            cuff_image_url = 'images/collarcuff/cuff 3.png'
        elif cuff_type == 'cuff4':
            cuff_image_url = 'images/collarcuff/cuff 4.png'
        elif cuff_type == 'cuff5':
            cuff_image_url = 'images/collarcuff/cuff 5.png'
        else:
            cuff_image_url = None 


        # Get or create the tailor instance
        tailor_instance = AddTailors.objects.get(id=tailor_id)
        works_on_delivery_date = Add_order.objects.filter(tailor=tailor_instance, delivery_date=dd).count()

        # if works_on_delivery_date >= 6:
        #     error_message = f"Tailor {tailor_instance.tailor} already has 6 or more works on {dd}. Cannot assign new work."
        #     if request.is_ajax():
        #         return JsonResponse({'error': error_message}, status=400)
        #     else:
        #         messages.error(request, error_message)
        #         return redirect('createcustomer')

        tailor_instance.assigned_works += 1
        tailor_instance.save()
        
        if cloth_id == '':
            cloth_id = None

        if not cloth_id and not existing_cloth_id:
            cloth_id = None

        try:
            if ordered_length_str:
                ordered_length = Decimal(ordered_length_str)
            elif cloth_id:
                ordered_length = Decimal(3.5)
            else:
                ordered_length = None
        except InvalidOperation:
            messages.error(request, "Invalid value for ordered length.")
            return redirect('customer_details')
        
        cloth = None
        if cloth_id:
            try:
                cloth = Cloth.objects.get(pk=cloth_id)
                cloth_name = cloth.name
                if cloth.stock_length >= ordered_length:
                    cloth.stock_length -= ordered_length
                    cloth.save()
                else:
                    messages.error(request, "Not enough cloth stock available.")
                    return redirect('customer_details')
            except Cloth.DoesNotExist:
                messages.error(request, "Cloth does not exist.")
                return redirect('customer_details')
        else:
            ordered_length = None

        # Get or create the tailor instance
        customer_instance = Customer.objects.get(id=id)
        try:
            # Generate a unique bill_number sequentially
            last_bill_number = Add_order.objects.order_by('-bill_number').first()

            if last_bill_number:
                last_bill_chars = last_bill_number.bill_number[:1]  # Extract the first character
                last_bill_digits = int(last_bill_number.bill_number[1:])  # Extract the digits

                if last_bill_chars == 'Z' and last_bill_digits == 999:
                    raise ValueError("Cannot generate more bills")
                elif last_bill_digits == 999:
                    next_chars = chr(ord(last_bill_chars) + 1)  # Increment the character
                    if next_chars > 'Z':  # Check if the next character exceeds 'Z'
                        raise ValueError("Cannot generate more bills")
                    bill_number = f"{next_chars}001"  # Reset digits to "001"
                else:
                    bill_number = f"{last_bill_chars}{last_bill_digits + 1:03d}"  # Increment digits
            else:
                bill_number = "A001"


            # Create the customer instance
            obj = Add_order(customer_id=customer_instance, length=ln, shoulder=sd, loose=lo, regal=rg,
                bill_number=bill_number, model_details=model_details,
                cuff_measurements=cuff_measurment, collar_type_image_url=collar_image_url,
                cuff_type_image_url=cuff_image_url, collar_measurements=collar_measurment,
                collar_type=collar_type, cuff_type=cuff_type, center_sleeve=center_sleeve,
                sleeve_sada=sl, sleeve_cuff=sll, pocket=po, bottom1=b1, seat=b2,
                order_date=od, total_payment=tp, advance_payment=ap, balance_payment=bp,
                delivery_date=dd, tailor=tailor_instance, button_type=bt,cloth_name=cloth_name,
                description=other, sleeve_bottom=sb,clothdetails=cloth,ordered_length=ordered_length,
                pocket_image_url=pocket_image_url,pocket_type=pocket_type)

            obj.save()

            messages.success(request, f"Successfully added new order: {obj.customer_id.name}")
            return redirect('add_order', dataid=obj.customer_id.id)

        except IntegrityError as e:
            # Handle IntegrityError
            return JsonResponse({'error': f"IntegrityError: {str(e)}"}, status=500)
        except Exception as e:
            # Handle other exceptions
            return JsonResponse({'error': f"Error saving customer: {str(e)}"}, status=500)

    return redirect(order_details)

def search_tailor(request):
    results = {'tailors': []}
    query = ""

    if 'q' in request.GET:
        query = request.GET['q']
        results['tailors'] = AddTailors.objects.filter(mobile_number__icontains=query)

    return render(request, 'search_tailor.html', {'results': results, 'query': query})


def tailor_work_details(request):
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        tailors = AddTailors.objects.all()

        tailor_data = []
        for tailor in tailors:
            assigned_works = Add_order.objects.filter(
                tailor=tailor, status='assigned', order_date__range=[start_date, end_date]
            ).count()

            pending_works = Add_order.objects.filter(
                tailor=tailor, status='in_progress', order_date__range=[start_date, end_date]
            ).count()

            completed_works = Add_order.objects.filter(
                tailor=tailor, status='completed', order_date__range=[start_date, end_date]
            ).count()

            tailor_info = {
                'tailor': tailor,
                'assigned_works': assigned_works,
                'pending_works': pending_works,
                'completed_works': completed_works
            }

            tailor_data.append(tailor_info)

        context = {
            'tailor_data': tailor_data,
            'start_date': start_date,
            'end_date': end_date,
        }

        return render(request, 'tailor_details.html', context)

    return render(request, 'tailor_work.html')


def select_dates(request):
    return render(request, "tailor_work.html")


from datetime import datetime


def tailor_appointments(request):
    # Retrieve start_date and end_date from the POST request
    start_date_str = request.POST.get('start_date')
    end_date_str = request.POST.get('end_date')

    # Convert start_date_str and end_date_str to datetime objects
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    # Get all tailors
    tailors = AddTailors.objects.all()

    # Initialize list to store tailor data
    tailor_data = []

    # Iterate through each tailor
    for tailor in tailors:
        # Filter customer orders for the tailor within the date range
        tailor_orders = Add_order.objects.filter(
            tailor=tailor,
            # order_date__gte=start_date,
            delivery_date__lte=end_date,
        )

        # Count the number of orders in each status for the tailor within the date range
        assigned_works = tailor_orders.filter(status='assigned').count()
        pending_works = tailor_orders.filter(status='in_progress').count()
        completed_works = tailor_orders.filter(status='completed').count()

        # Append tailor data to the list
        tailor_data.append({
            'tailor': tailor,
            'assigned_works': assigned_works,
            'pending_works': pending_works,
            'completed_works': completed_works,
        })

    # Pass the results to the template
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'tailor_data': tailor_data,
    }

    return render(request, 'tailor_details.html', context)
from django.conf import settings
from django.db.models import Sum
from datetime import date

def login(request):
    if request.method == "POST":
        un = request.POST.get('user_name')
        pwd = request.POST.get('password')
        
        # Check if the user is an admin
        if admin_login.objects.filter(username=un, password=pwd).exists():
            request.session['user_name'] = un
            request.session['password'] = pwd
            messages.success(request, "Login Successful")
            # Calculating data for the dashboard
            total_customers = Customer.objects.count()
            total_order = Add_order.objects.count()
            total_completed_works = AddTailors.objects.aggregate(Sum('completed_works'))['completed_works__sum']
            cus = Add_order.objects.filter(delivery_date__gte=date.today()).order_by('delivery_date')

            context = {
                'total_customers': total_customers,
                'total_orders': total_order,
                'cus': cus,
                'total_completed_works': total_completed_works  
            }

            return render(request, 'dashboard.html', context=context)
        
        # Check if the user is a receptionist
        elif reception_login.objects.filter(user_name=un, password=pwd).exists():
            request.session['username'] = un
            request.session['password'] = pwd
            messages.success(request, "Login Successful")
            total_customers = Customer.objects.count()
            total_order = Add_order.objects.count()  # Assuming you have an Order model
            total_completed_works = AddTailors.objects.aggregate(Sum('completed_works'))['completed_works__sum']
            cus = Add_order.objects.filter(delivery_date__gte=date.today()).order_by('delivery_date')

            context = {
                'total_customers': total_customers,
                'total_orders': total_order,
                'cus': cus,
                'total_completed_works': total_completed_works
            }
            return render(request, 'reception_dashboard.html',context=context)  # Render the receptionist dashboard template
        
        else:
            messages.warning(request, "Please Enter Valid username and password...")
            print("Login failed")
            return render(request, 'login.html')  # Render the login page again with a warning message
    else:
        # Check if user is already logged in
        if 'user_name' in request.session:
            total_customers = Customer.objects.count()
            total_order = Add_order.objects.count()
            total_completed_works = AddTailors.objects.aggregate(Sum('completed_works'))['completed_works__sum']
            cus = Add_order.objects.filter(delivery_date__gte=date.today()).order_by('delivery_date')

            context = {
                'total_customers': total_customers,
                'total_orders': total_order,
                'cus': cus,
                'total_completed_works': total_completed_works
            }
            return render(request, 'dashboard.html',context=context)  # Render the admin dashboard if already logged in
        elif 'username' in request.session:
            total_customers = Customer.objects.count()
            total_order = Add_order.objects.count()  # Assuming you have an Order model
            total_completed_works = AddTailors.objects.aggregate(Sum('completed_works'))['completed_works__sum']
            cus = Add_order.objects.filter(delivery_date__gte=date.today()).order_by('delivery_date')

            context = {
                'total_customers': total_customers,
                'total_orders': total_order,
                'cus': cus,
                'total_completed_works': total_completed_works
            }
            return render(request, 'reception_dashboard.html',context)  # Render the receptionist dashboard if already logged in
        else:
            print(settings.TEMPLATES[0]['DIRS'])  # Debugging: Print template directories
            return render(request, 'login.html')  # Render the login page  # Render the login page


    
def savelogin(request):
    if request.method == "POST":
        un = request.POST.get('user_name')
        pd = request.POST.get('password')
        obj = admin_login(username=un, password=pd)
        obj.save()
        return render(savelogin)


def adminlogin(request):
    pass

@never_cache
def LogoutAdmin(request):
    if 'user_name' in request.session:
        del request.session['user_name']
    if 'password' in request.session:
        del request.session['password']
    messages.success(request, 'Logout successful...!')
    response = redirect('login')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@never_cache
def LogoutReception(request):
    if 'username' in request.session:
        del request.session['username']
    if 'password' in request.session:
        del request.session['password']
    messages.success(request, 'Logout successful...!')
    response = redirect('login')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

from django.contrib.auth.decorators import login_required
from django.utils.cache import add_never_cache_headers


@login_required
def some_protected_view(request):
    # Your view logic goes here
    # For example:
    # Your view logic...

    # Create the HTTP response
    response = HttpResponse()

    # Set cache-control headers to prevent caching
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    return response
class NoCacheMiddleware:

    def _init_(self, get_response):
        self.get_response = get_response

    def _call_(self, request):
        response = self.get_response(request)
        add_never_cache_headers(response)
        return response
